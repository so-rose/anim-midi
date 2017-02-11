import jack

from .device import STATUS_TYPE

#The process function.

def jack_proc(q, cmdQ, STATUS_TYPE) :	
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
		while True :
			msg = cmdQ.get()
			if msg == "IS_ACTIVE": cmdQ
			elif msg == "QUIT": break
		
