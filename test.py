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
from collections import deque

sys.path.append('/usr/local/lib/python3.5/dist-packages') #Needed for internal blender to see modules.

#CONSTANTS

FPS = 24 #Set for smoothness vs. Performance.
SAMPLE_FAC = 1 #The number of times per frame that the MIDI controls are sampled.

#Settings ^^ higher would require decreasing the processing time in the modal.

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
					113 : 'FWD',
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

###############################################################################################
#PUT IN SEPERATE SCRIPT

def anim_bind(button, *bProp, iRange=(0, 127), oRange=(0.0, 1.0), isOp=False, isBool=False, iFunc=lambda x: x) : #Blneder Properties can't be bound here.
	"""
	Manipulate the numeric value at the list of data locations bProp in blender, by
	making the data coming from CONTROL signals on button (a string defined in BUT_MAP) into
	live data manipulation.
	
	iRange is the midi signal range, oRange is the Blender knob range.
	
	iFunc is an optional interpolation function.
	
	If isOp is true, then the blender_prop is an operator to call, and iRange/oRange/interp is useless.
	If isBool is true, then the blender_prop is a boolean value. iRange[1] and iRange[0] will map to True/False by rounding.
	"""
	
	#~ dest_map = dest if dest else BLEND_MAP
	
	return {				'button' : button,
							'isOp' : isOp,
							'isBool' : isBool,
							'blender_prop' : bProp,
							'input_range' : iRange,
							'output_range' : oRange,
							'interp' : iFunc
	}
	
def gen_RAT_FACE() :
	RAT_FACE = {}
	
	eye_R = "bpy.data.objects['rig'].pose.bones['CTRL_eye_R']"
	eye_L = "bpy.data.objects['rig'].pose.bones['CTRL_eye_L']"
	rig = "bpy.data.objects['rig']"
	face = "bpy.data.objects['rig'].pose.bones['CTRL_face']"


	RAT_FACE['FADER_1'] = anim_bind('FADER_1', face + "['mouth']")
	RAT_FACE['KNOB_1'] = anim_bind('KNOB_1', eye_R + "['eye_back']", eye_R + "['eye_lower']", eye_R + "['eye_upper']")
	RAT_FACE['KNOB_5'] = anim_bind('KNOB_5', eye_L + "['eye_back']", eye_L + "['eye_lower']", eye_L + "['eye_upper']")
	RAT_FACE['KNOB_2'] = anim_bind('KNOB_2', rig + '.pose.bones["CTRL_face"]["corner_R"]')
	RAT_FACE['KNOB_6'] = anim_bind('KNOB_6', rig + '.pose.bones["CTRL_face"]["corner_L"]')
	RAT_FACE['KNOB_3'] = anim_bind('KNOB_3', rig + '.pose.bones["CTRL_face"]["neck_bulge"]')
	RAT_FACE['KNOB_7'] = anim_bind('KNOB_7', rig + '.pose.bones["CTRL_face"]["neck_lungs"]')
	RAT_FACE['KNOB_4'] = anim_bind('KNOB_4', rig + '.pose.bones["CTRL_face"]["cheek_back_R"]', iFunc=lambda x: x * 2)
	RAT_FACE['KNOB_8'] = anim_bind('KNOB_8', rig + '.pose.bones["CTRL_face"]["cheek_back_L"]', iFunc=lambda x: x * 2)
	RAT_FACE['REW'] = anim_bind('REW', 'bpy.ops.screen.keyframe_jump(next=False)', isOp=True)
	RAT_FACE['FWD'] = anim_bind('FWD', 'bpy.ops.screen.keyframe_jump(next=True)', isOp=True)
	RAT_FACE['LOOP'] = anim_bind('LOOP', 'bpy.ops.screen.frame_jump(end=False)', isOp=True)
	RAT_FACE['PLAY'] = anim_bind('PLAY', 'bpy.ops.screen.animation_play()', isOp=True)
	RAT_FACE['REC'] = anim_bind('REC', 'context.scene.tool_settings.use_keyframe_insert_auto', isBool=True)
	#~ anim_bind('MOD_WHL', rig + ".pose.bones['body_hind'].rotation_euler[0]", oRange=(math.radians(-7.0), math.radians(20.0)))
	RAT_FACE['MOD_WHL'] = anim_bind('MOD_WHL', rig + '.pose.bones["CTRL_face"]["nose"]')
		
	return RAT_FACE

MAPS = {	'RAT_FACE' : gen_RAT_FACE()

}

###############################################################################################


#The queues.
q = mp.Queue() #For the JACK process to send data to Blender.
cmdQ = mp.Queue() #To send commands to the JACK process.

#Helper Functions
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


def scaleRange(val, iRange, oRange):
	outVal = (((val - iRange[0]) * (oRange[1] - oRange[0])) / (iRange[1] - iRange[0])) + oRange[0]
	if outVal > oRange[1]: return oRange[1]
	elif outVal < iRange[0]: return iRange[0]
	else: return outVal

def m2f(note):
	"""Convert MIDI note number to a hz freq

	https://en.wikipedia.org/wiki/MIDI_Tuning_Standard.
	
	Cool idea: Play rig animation as MIDI notes?
	
	"""
	return 2 ** ((note - 69) / 12) * 440

#The process function.

def process(q, cmdQ, STATUS_TYPE) :	
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
						q.put( (STATUS_TYPE[status], pitch, vel) )
				except :
					print("Status not mapped!")
					
	
	with client:
		#Blocks until QUIT is passed over cmdQ queue.
		try: client.connect("a2j:Impulse [24] (capture): Impulse MIDI 1", midi_in)
		except: pass
		while True :
			msg = cmdQ.get()
			if msg == "IS_ACTIVE": cmdQ
			elif msg == "QUIT": break
		

#Blender addon stuff.

class ModalTimerOperator(bpy.types.Operator):
	"""Operator which runs its self from a timer"""
	bl_idname = "wm.modal_timer_operator"
	bl_label = "Modal Timer Operator"

	_timer = None
	#~ CHOICE = 0

	def modal(self, context, event):
		if event.type in {'ESC'}:
			self.cancel(context)
			return {'CANCELLED'}

		if event.type == 'TIMER':
			#Do cool things.
			
			#Dequeue all new signal data.
			newItems = []
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
					
			try:
				binds = [BLEND_MAP[CHAN_MAP[item[1]]] for item in items]
			except :
				print("Button Not Mapped: {0}".format(CHAN_MAP[item[1]]))
				self.report({'INFO'}, 'Button Not Mapped: {0}'.format(CHAN_MAP[item[1]]))
				return {'PASS_THROUGH'}
			#~ print(binds)
							
			for i in range(len(items)) :
				if binds[i]['isOp'] :
					if CHAN_MAP[items[i][1]] == binds[i]['button'] :
						for bProp in binds[i]['blender_prop'] :
							if items[i][2] == binds[i]['input_range'][1] :
								exec('{0}'.format(bProp))
								
				elif binds[i]['isBool'] :
					val_nrm = scaleRange(items[i][2], binds[i]['input_range'], (0, 1))
					print(val_nrm)
					
					if CHAN_MAP[items[i][1]] == binds[i]['button'] :
						for bProp in binds[i]['blender_prop'] :
							if round(val_nrm) == 1 :
								exec("{0} = {1}".format(bProp, True))
							elif round(val_nrm) == 0 :
								exec("{0} = {1}".format(bProp, False))
								
				else :
					val_nrm = scaleRange(items[i][2], binds[i]['input_range'], (0, 1))
					val_interp = binds[i]['interp'](val_nrm) #Call the attached interpolation function on the normalized value.
					#~ print(val_interp)
					bVal = scaleRange(val_interp, (0, 1), binds[i]['output_range'])
				
					if CHAN_MAP[items[i][1]] == binds[i]['button'] :
						for bProp in binds[i]['blender_prop'] :
							exec("{0} = {1}".format(bProp, bVal))
						
			#Update all meshes in scene.
			for obj in context.scene.objects :
				if obj.type == 'MESH': obj.data.update()
			
		return {'PASS_THROUGH'}

	def execute(self, context):
		wm = context.window_manager
		self._timer = wm.event_timer_add(1/(SAMPLE_FAC*FPS), context.window)
		wm.modal_handler_add(self)
		return {'RUNNING_MODAL'}

	def cancel(self, context):
		wm = context.window_manager
		wm.event_timer_remove(self._timer)
		cmdQ.put('QUIT')
		proc.terminate()
		print("Quit anim-midi!")


def register():
	bpy.utils.register_class(ModalTimerOperator)


def unregister():
	bpy.utils.unregister_class(ModalTimerOperator)


if __name__ == "__main__":
	BLEND_MAP = MAPS['RAT_FACE']
	
	proc = mp.Process(target=process, args=(q, cmdQ, copy.deepcopy(STATUS_TYPE)))
	proc.start()
	
	register()
	
	#Test Call
	bpy.ops.wm.modal_timer_operator()
	
