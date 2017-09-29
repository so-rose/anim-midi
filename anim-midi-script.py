#!/usr/bin/env python3

"""
What can I say. It works. Load it into the text editor and tap run script to enjoy MIDI animation.

Features includes:
- Weirdest fucking mapping interface. Dig deep into the modal operator
to map simple Blender properties to the MIDI stream.

- Super laggy and slow during animation!
- Two frame changes per MIDI event. Why you ask? To update the scene. Can't find a better way...
- Only one device supported - Novation Impulse 25 key
- MIDI stuff runs in a thread! RIP GIL. Perhaps it should run in a - PROCESS..?

- Supports - no, REQUIRES - jack! Jack MIDI input is real & kicking.
^^ That's a feature by the way

- Rig specific for now. But beautifully so :).
- Seriously this is cool shit...

- Oh yeah: pip install JACK-Client . Make sure you're on Linux or Mac(?) and not the one we don't talk about ;)

"""

import math, sys, copy, time, struct
import multiprocessing as mp

sys.path.append('/usr/local/lib/python3.5/dist-packages') #Needed for internal blender to see modules.

#CONSTANTS

q = mp.Queue() #For JACK --> Curator process communication..
cmdJQ = mp.Queue() #For main --> JACK process communication.
curQ = mp.Queue() #For Curator --> main process communication

FPS = 5 #Set for smoothness vs. Performance.
SAMPLE_FAC = 1 #The number of times per frame that the MIDI controls are sampled.

#Decimal Representations of MIDI statuses for various controls on my Novation Impulse. From reading struct.unpack('3B', data) in process().

STATUS_TYPE = {		144 : 'NOTEDOWN',
					128 : 'NOTEUP',
					176 : 'CONTROL',
					224 : 'PITCH_MOD'
}

#Channel --> Button Name on my Novation Impulse 25.

CHAN_MAP = {		49	: 'FADER_1',
					21	: 'KNOB_1',
					22	: 'KNOB_2',
					23	: 'KNOB_3',
					24	: 'KNOB_4',
					25	: 'KNOB_5',
					26	: 'KNOB_6',
					27	: 'KNOB_7',
					28	: 'KNOB_8',
					1	: 'MOD_WHL',
					115 : 'PLAY',
					114 : 'STOP',
					112 : 'REW',
					123 : 'FWD',
					117 : 'REC',
					116 : 'LOOP'
}

#Button Name --> Channel on my Novation Impulse 25.
BUT_MAP = {v : k for k, v in CHAN_MAP.items()}

#The map of Buttons to Blender RNA paths to manipulate. Filled later.
BLEND_MAP = {} #See anim_bind for construction.

MOD_BLENDER = False
try :
	import bpy
	MOD_BLENDER = True
except :
	print('Blender bpy module not found! Mappings won\'t work!')

import jack

#Helper Functions
def m2f(note):
	"""Convert MIDI note number to a hz freq

	https://en.wikipedia.org/wiki/MIDI_Tuning_Standard.
	
	Cool idea: Play rig animation as MIDI notes?
	
	"""
	return 2 ** ((note - 69) / 12) * 440

def anim_bind(button, *bProp, iRange=(0, 127), oRange=(0.0, 1.0), iFunc=lambda x: x) : #Blneder Properties can't be bound here.
	"""
	Manipulate the numeric value at the list of RNA data locations bProp in blender, by
	making the data coming from CONTROL signals on button (a string defined in BUT_MAP) into
	live data manipulation.
	
	iRange is the midi signal range, oRange is the Blender knob range.
	
	iFunc is an optional interpolation function.
	"""
	BLEND_MAP[button] = {	'button' : button,
							'blender_prop' : bProp,
							'input_range' : iRange,
							'output_range' : oRange,
							'interp' : iFunc,
	}
	
#Only use the newest (last) item of each channel to update.
class Data :
	def __init__(self, chnls, items, bVals, picklable=False) :
		"""
		"""
		self.picklable = picklable
		self.items = tuple(items)
		try :
			if picklable :
				#To be picklable, we must exclude the interpolation function. It's not needed, anyhow.
				self.binds = tuple([ {k: v for k, v in BLEND_MAP[CHAN_MAP[item[1]]].items() if k != 'interp'} for item in items])
			else :
				self.binds = tuple([BLEND_MAP[CHAN_MAP[item[1]]] for item in items])
		except :
			raise ValueError('Button not bound! MIDI channel #s processed:', [item[1] for item in items])
			
		self.bVals = tuple(bVals)
		self.chnls = tuple(chnls)
		
	def __len__(self) :
		return len(self.items)
		
	def __iter__(self) :
		return iter([{'item' : item, 'bind' : bind, 'bVal' : bVal} for item, bind, bVal in zip(self.items, self.binds, self.bVals)])
		
	def __repr__(self) :
		return "Data({0}, {1}, {2}, picklable={3})".format(self.chnls, self.items, self.bVals, self.picklable)

#The process function.

def jack_proc(q, cmdJQ, STATUS_TYPE) :	
	#Setup Jack
	client = jack.Client('anim-midi')
	midi_in = client.midi_inports.register('input')
	#~ audio_out = client.outports.register('audio')
	
	@client.set_process_callback
	def process(frames):
		for offset, data in midi_in.incoming_midi_events():
			if len(data) == 3:
				status, pitch, vel = struct.unpack('3B', data)
				#Status meanings are in STATUS_TYPE.
				#Pitch is the CC# - the MIDI channel/note value.
				
				try:
					if STATUS_TYPE[status] == 'CONTROL' :
						#~ print("[JACK MIDI]", STATUS_TYPE[status], pitch, vel)
						q.put( (STATUS_TYPE[status], pitch, vel, 0) )
						#signalType, channel #, value, bVal (not yet set)
				except :
					print("Status not mapped!")
					
	with client:
		#Blocks until QUIT is passed over cmdQ queue.
		client.connect("a2j:Impulse [24] (capture): Impulse MIDI 1", midi_in)
		while True :
			msg = cmdJQ.get()
			if msg == "QUIT": break
			
#Think of this as the middleware process
def cur_proc(q, curQ) :
	def scaleRange(val, iRange, oRange): return (((val - iRange[0]) * (oRange[1] - oRange[0])) / (iRange[1] - iRange[0])) + oRange[0]
	
	curTime = time.perf_counter()
	dT = 0
	while True :
		time.sleep(1/(SAMPLE_FAC*FPS))
		if dT >= 1/FPS : #Don't run too often.
			try :
				first = q.get(block=False) #Block until a signal arrives.
			except :
				dT += time.perf_counter() - curTime
				curTime = time.perf_counter()
				continue
			#Dequeue all new signal data.
			tStart = time.perf_counter()
			newItems = [first]
			while not q.empty() :
				newItems.append(q.get(block=False))
				
			chnls = []
			items = []
			for item in newItems[::-1] : #Reversed so we get the newest item.
				if item[1] not in chnls : #Never seen this channel before.
					chnls.append(item[1]) #Append the channel to the list of channels.
					items.append(item) #Append the item to the list of items.
				else :
					continue
					
			try :
				incData = Data(chnls, items, [0 for i in range(len(items))]) #Not yet complete.
			except Exception as e :
				print(repr(e))
				continue
							
			bVals = []
			for d in incData :
				#~ print(d)
				val_nrm = scaleRange(d['item'][2], d['bind']['input_range'], (0, 1))
				val_interp = d['bind']['interp'](val_nrm) #Call the attached interpolation function on the normalized value.
				bVals.append(scaleRange(val_interp, (0, 1), d['bind']['output_range']))
							
			data = Data(chnls, items, bVals, picklable=True)
			
			#~ print(data)
			
			curQ.put( tuple(data) )
			
		dT += time.perf_counter() - curTime
		curTime = time.perf_counter()
	
class ModalTimerOperator(bpy.types.Operator):
	"""Operator which runs its self from a timer"""
	bl_idname = "wm.modal_timer_operator"
	bl_label = "Modal Timer Operator"

	_timer = None
	CHOICE = 0

	def modal(self, context, event):
		if event.type in {'ESC'}:
			self.cancel(context)
			return {'CANCELLED'}

		if event.type == 'TIMER':
			print('hi')
			try :
				data = q.get(block=False)
			except :
				print("Queue empty")
				return {'PASS_THROUGH'}
			
			print(data)
			
			if not data: return {'PASS_THROUGH'}
			
			#Update all properties from each bind/item pair.
			for d in data :
				if CHAN_MAP[d['item'][1]] == d['bind']['button'] :
					for bProp in d['bind']['blender_prop'] :
						#~ print("{0} = {1}".format(bProp, data['bVal']))
						exec("{0} = {1}".format(bProp, data['bVal']))
						
			#Try bpy.data.objects['rig'].children[0].data.update()
			if not self.CHOICE: bpy.context.scene.frame_set(bpy.context.scene.frame_current + 1); self.CHOICE = 1
			if self.CHOICE: bpy.context.scene.frame_set(bpy.context.scene.frame_current - 1); self.CHOICE = 0
			
		return {'PASS_THROUGH'}

	def execute(self, context):
		wm = context.window_manager
		self._timer = wm.event_timer_add(1/(SAMPLE_FAC*FPS), context.window)
		wm.modal_handler_add(self)
		return {'RUNNING_MODAL'}

	def cancel(self, context):
		wm = context.window_manager
		wm.event_timer_remove(self._timer)
		jackProc.terminate()
		curProc.terminate()
		print("Quit anim-midi!")


def register():
	bpy.utils.register_class(ModalTimerOperator)


def unregister():
	bpy.utils.unregister_class(ModalTimerOperator)


if __name__ == "__main__":
	#Bind an example BLEND_MAP. 
	rig = "bpy.data.objects['rig']"
	face = "bpy.data.objects['rig'].pose.bones['CTRL_face']"
	
	eye_R = "bpy.data.objects['rig'].pose.bones['CTRL_eye_R']"
	eye_L = "bpy.data.objects['rig'].pose.bones['CTRL_eye_L']"
	
	anim_bind('FADER_1', face + "['mouth']")
	anim_bind('KNOB_1', eye_R + "['eye_back']", eye_R + "['eye_lower']", eye_R + "['eye_upper']")
	anim_bind('KNOB_5', eye_L + "['eye_back']", eye_L + "['eye_lower']", eye_L + "['eye_upper']")
	anim_bind('KNOB_8', face + "['nose']")
	anim_bind('KNOB_8', face + "['nose']")
	anim_bind('MOD_WHL', rig + ".pose.bones['body_hind'].rotation_euler[0]", oRange=(math.radians(-7.0), math.radians(20.0)))
	
	print(BLEND_MAP)
	
	register()
	
	jackProc = mp.Process(target=jack_proc, args=(q, cmdJQ, copy.deepcopy(STATUS_TYPE)))
	jackProc.start()
	
	curProc = mp.Process(target=cur_proc, args=(q, curQ))
	curProc.start()
	
