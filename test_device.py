#!/bin/env python3

import math, sys, copy, time, struct

import jack

STATUS_TYPE = {		144 : 'NOTEDOWN',
					128 : 'NOTEUP',
					176 : 'CONTROL',
					224 : 'PITCH_MOD'
}

#Setup Jack
client = jack.Client('test_device')
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
					print("[JACK MIDI]", STATUS_TYPE[status], pitch, vel, end="     \r")
			except :
				print("Status not mapped!")
				
with client:
    input()
