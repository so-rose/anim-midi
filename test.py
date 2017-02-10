#!/usr/bin/env python3

"""
What can I say. It works. Load it into the text editor and tap run script to enjoy MIDI animation.

Features includes:
- A bit laggy and slow.
- Weirdest fucking mapping interface. Dig deep into the modal operator
to map simple Blender properties to the MIDI stream.
- By the way. There has to be a better way to stream data across threads than a FUCKING QUEUE.

- Interpolation functions... Lol no too slow. Maybe.
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

import sys
import multiprocessing as mp

import bpy
import time
import threading

MOD_BLENDER = False
try :
	import bpy
	sys.path.append('/usr/local/lib/python3.5/dist-packages') #Needed for internal blender to see modules.
	MOD_BLENDER = True
except :
	print('Blender bpy module not found! Mappings won\'t work!')

def process(q, STATUS_TYPE) :
	import math, sys
	sys.path.append('/usr/local/lib/python3.5/dist-packages') #Needed for internal blender to see modules.
	
	import jack
	import struct

	#Setup Jack
	client = jack.Client('anim-midi')
	midi_in = client.midi_inports.register('input')
	#~ audio_out = client.outports.register('audio')
	
	#Helper Functions
	def m2f(note):
		"""Convert MIDI note number to a hz freq

		https://en.wikipedia.org/wiki/MIDI_Tuning_Standard.
		
		Cool idea: Play rig animation as MIDI notes?
		
		"""
		return 2 ** ((note - 69) / 12) * 440
		
	
	@client.set_process_callback
	def process(frames):
		for offset, data in midi_in.incoming_midi_events():
			if len(data) == 3:
				status, pitch, vel = struct.unpack('3B', data)
				#Status meanings are in STATUS_TYPE.
				#Pitch is the CC# - the channel pitch.
				
				print(STATUS_TYPE[status], pitch, vel)
				
				if STATUS_TYPE[status] == 'CONTROL' :
					q.put( (STATUS_TYPE[status], pitch, vel) )
					
	with client:
		print('#' * 80)
		print('press Return to quit')
		print('#' * 80)
		input()


#Decimal Representations of MIDI statuses for various controls on my Novation Impulse. From reading struct.unpack('3B', data) in process().

STATUS_TYPE = {		144 : 'NOTEDOWN',
					128 : 'NOTEUP',
					176 : 'CONTROL',
					224 : 'PITCH_MOD'
}

#Channel --> Button Name on my Novation Impulse 25.

CHAN_MAP = {		49 : 'FADER_1',
					21 : 'KNOB_1',
					22 : 'KNOB_2',
					23 : 'KNOB_3',
					24 : 'KNOB_4',
					25 : 'KNOB_5',
					26 : 'KNOB_6',
					27 : 'KNOB_7',
					28 : 'KNOB_8',
					115 : 'PLAY',
					114 : 'STOP',
					112 : 'REW',
					123 : 'FWD',
					117 : 'REC',
					116 : 'LOOP'
}

BUT_MAP = {v : k for k, v in CHAN_MAP.items()} #Button Name --> Channel on my Novation Impulse 25.

#The map of Buttons to Blender RNA paths to manipulate.

BLEND_MAP = {}

def anim_bind(button, iRange=(0, 127), oRange=(0.0, 1.0), iFunc=lambda x: x) : #Blneder Properties can't be bound here.
	"""
	Manipulate the numeric value at the RNA data location bProp in blender, by
	making the data coming from CONTROL signals on button (a string defined in BUT_MAP) into
	live data manipulation.
	
	iRange is the midi signal range, oRange is the Blender knob range.
	
	iFunc is an optional interpolation function.
	"""
	bProp = "not_implemented" #This is an issue
	BLEND_MAP[button] = {	'blender_prop' : bProp,
							'input_range' : iRange,
							'output_range' : oRange,
							'interp' : iFunc
	}
	
def scaleRange(val, iRange, oRange): return (((val - iRange[0]) * (oRange[1] - oRange[0])) / (iRange[1] - iRange[0])) + oRange[0]

#Bind an example BLEND_MAP. 
anim_bind('FADER_1')
anim_bind('KNOB_1')
anim_bind('KNOB_5')
anim_bind('KNOB_8')


class Worker(threading.Thread) :
	def __init__(self, *args) :
		self.args = args
		threading.Thread.__init__(self)
		
	def run(self) :
		process(*self.args)

q = mp.Queue()
FPS=30 #Set for smoothness vs. Performance.

class ModalTimerOperator(bpy.types.Operator):
	"""Operator which runs its self from a timer"""
	bl_idname = "wm.modal_timer_operator"
	bl_label = "Modal Timer Operator"

	_timer = None
	curTime = time.time()

	def modal(self, context, event):
		if event.type in {'ESC'}:
			self.cancel(context)
			return {'CANCELLED'}

		if event.type == 'TIMER':
			#Do cool things.
			#~ print(q.empty())
			
			try:
				item = q.get(block=False)
			except :
				return {'PASS_THROUGH'}
			
			try :
				bind = BLEND_MAP[CHAN_MAP[item[1]]]
			except :
				print('Button not bound!')
				return {'PASS_THROUGH'}
			
			#~ print(bind)
			
			val_nrm = scaleRange(item[2], bind['input_range'], (0, 1))
			#~ val_interp = bind['interp'](val_nrm) #Call the attached interpolation function on the normalized value.
			#~ bVal = scaleRange(val_interp, (0, 1), bind['output_range'])
			bVal = val_nrm
			
			#~ print('\t', bVal, bpy.data.objects['rig'].pose.bones["CTRL_face"]["mouth"])
			
			#~ bind['blender_prop'] = bVal
			if CHAN_MAP[item[1]] == "FADER_1" :
				bpy.data.objects['rig'].pose.bones["CTRL_face"]["mouth"] = bVal
			if CHAN_MAP[item[1]] == "KNOB_1" :
				bpy.data.objects['rig'].pose.bones["CTRL_eye_R"]["eye_back"] = bVal
				bpy.data.objects['rig'].pose.bones["CTRL_eye_R"]["eye_lower"] = bVal
				bpy.data.objects['rig'].pose.bones["CTRL_eye_R"]["eye_upper"] = bVal
			if CHAN_MAP[item[1]] == "KNOB_5" :
				bpy.data.objects['rig'].pose.bones["CTRL_eye_L"]["eye_back"] = bVal
				bpy.data.objects['rig'].pose.bones["CTRL_eye_L"]["eye_lower"] = bVal
				bpy.data.objects['rig'].pose.bones["CTRL_eye_L"]["eye_upper"] = bVal
			if CHAN_MAP[item[1]] == "KNOB_8" :
				bpy.data.objects['rig'].pose.bones["CTRL_face"]["nose"] = bVal
			
			#~ bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
			#~ bpy.context.scene.update()
			
			#~ print(bpy.data.objects['rig'].pose.bones["CTRL_face"]["mouth"])
			
			if time.time() > self.curTime + 1/FPS :
				#~ bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
				CHOICE=0
				if not CHOICE: bpy.context.scene.frame_set(bpy.context.scene.frame_current + 1); CHOICE = 1
				if CHOICE: bpy.context.scene.frame_set(bpy.context.scene.frame_current - 1); CHOICE = 0
				self.curTime = time.time()
			
		return {'PASS_THROUGH'}

	def execute(self, context):
		wm = context.window_manager
		self._timer = wm.event_timer_add(0.0001, context.window)
		wm.modal_handler_add(self)
		return {'RUNNING_MODAL'}

	def cancel(self, context):
		wm = context.window_manager
		wm.event_timer_remove(self._timer)


def register():
	bpy.utils.register_class(ModalTimerOperator)


def unregister():
	bpy.utils.unregister_class(ModalTimerOperator)


if __name__ == "__main__":
	register()
	
	thread = Worker(q, STATUS_TYPE)
	thread.start()

	# test call
	bpy.ops.wm.modal_timer_operator()
