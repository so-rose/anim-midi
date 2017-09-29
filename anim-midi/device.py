'''
This file defines device mappings, as well as a universal device mapping. The
idea being, any device can map to the universal device mapping, which then
maps to whatever program.

checkStatus returns the Status Type of the raw jack-supplied arg, status.

Status Types:
	- NOTEDOWN - When the note is pressed.
	- NOTEUP - When the note is pulled up.
	- CONTROL - MIDI control signal.
	- PITCH_MOD - Pitch control.
	- POLY_AFTER - Aftertouch, with pressure.
	- PROG_CHG - Program Change signal.
	- CHNL_AFTER - Aftertouch, all or nothing.
	
CONTROL Buttons:
	Channel:
	- FADER_n - the nth channel fader (slides) on the device.
	- KNOB_n - the nth channel knob (turns) on the device.
	- SOLO_n - the nth channel solo button.
	- MUTE_n - the nth channel mute button.
	- REC_n - the nth channel record button.
	
	Transport:
	- PLAY - the play button.
	- STOP - the stop button.
	- REW - the rewind button.
	- FWD - the fast forward button.
	- REC - the global record button.
	- LOOP - the loop function button.
	
	Markers:
	- MARK_SET - the play button.
	- MARK_PREV - the play button.
	- MARK_NEXT - the play button.
	
	Track:
	- TRACK_PREV - Previous track.
	- TRACK_NEXT - Next track.
	
Universal Device:
	This is a universal mapping from names to a specialized mapping.
	
	Supports up to 20 channels.
	
	CONTROL (see above for ordering) :
		0 - 5: Transport.
		6 - 8: Markers
		9 - 10: Track
		11 - 27: Reserved
		28 - 47: Fader Channels
		48 - 67: Knob Channels
		68 - 87: Solo Channels
		88 - 107: Mute Channels
		108 - 127: Record Channels
		28 - 127: Channels
'''

#First 4 bits. Compare with 
STATUS_TYPE = {		0x9 : 'NOTEDOWN',
					0x8 : 'NOTEUP',
					0xB : 'CONTROL',
					0xE : 'PITCH_MOD',
					0xA	: 'POLY_AFTER',
					0xC	: 'PROG_CHG',
					0xD	: 'CHNL_AFTER'
}

STATUS_TYPE_REV = {v: k for k, v in STATUS_TYPE.items()}

#0-127 are the available pitches. See Documentation.
UNI_DEV = {	'offset' 	: 0,
		'PLAY'			: 0,
		'STOP'			: 1,
		'REW'			: 2,
		'FWD'			: 3,
		'REC'			: 4,
		'LOOP'			: 5,
		
		'MARK_SET'		: 6,
		'MARK_PREV'		: 7,
		'MARK_NEXT'		: 8,
		
		'TRACK_PREV'	: 9,
		'TRACK_NEXT'	: 10
}

#Finish off the dict with channel values
count = 0
for label in ('FADER', 'KNOB', 'SOLO', 'MUTE', 'REC') :
	for i in range(0, 20) :
		UNI_DEV[label + str(i)] = 28 + count
		count += 1

DEV = {
	"novation_impulse_25" :
		{	'offset' : 1,
			49	: 'FADER_0',
			21	: 'KNOB_0',
			22	: 'KNOB_1',
			23	: 'KNOB_2',
			24	: 'KNOB_3',
			25	: 'KNOB_4',
			26	: 'KNOB_5',
			27	: 'KNOB_6',
			28	: 'KNOB_7',
			1	: 'MOD_WHL',
			115 : 'PLAY',
			114 : 'STOP',
			112 : 'REW',
			113 : 'FWD',
			117 : 'REC',
			116 : 'LOOP'
		},
	"korg_nanokontrol_2" :
		{	'offset' : 0,
			0	: 'FADER_0',
			1	: 'FADER_1',
			2	: 'FADER_2',
			3	: 'FADER_3',
			4	: 'FADER_4',
			5	: 'FADER_5',
			6	: 'FADER_6',
			7	: 'FADER_7',
			16	: 'KNOB_0',
			17	: 'KNOB_1',
			18	: 'KNOB_2',
			19	: 'KNOB_3',
			20	: 'KNOB_4',
			21	: 'KNOB_5',
			22	: 'KNOB_6',
			23	: 'KNOB_7',
			32	: 'SOLO_0',
			33	: 'SOLO_1',
			34	: 'SOLO_2',
			35	: 'SOLO_3',
			36	: 'SOLO_4',
			37	: 'SOLO_5',
			38	: 'SOLO_6',
			39	: 'SOLO_7',
			48	: 'MUTE_0',
			49	: 'MUTE_1',
			50	: 'MUTE_2',
			51	: 'MUTE_3',
			52	: 'MUTE_4',
			53	: 'MUTE_5',
			54	: 'MUTE_6',
			55	: 'MUTE_7',
			64	: 'REC_0',
			65	: 'REC_1',
			66	: 'REC_2',
			67	: 'REC_3',
			68	: 'REC_4',
			69	: 'REC_5',
			70	: 'REC_6',
			71	: 'REC_7',
			41	: 'PLAY',
			42	: 'STOP',
			43	: 'REW',
			44	: 'FWD',
			45	: 'REC',
			46	: 'LOOP',
			60	: 'MARK_SET',
			61	: 'MARK_PREV',
			62	: 'MARK_NEXT',
			58	: 'TRACK_PREV',
			59	: 'TRACK_NEXT'
			
		},
	"universal" : UNI_DEV
}

DEV_REV = {k: {a: e for e, a in v.items()} for k, v in DEV.items()}

#Gives back the status type from the raw status consistently.
def checkStatus(status): return STATUS_TYPE[status >> 4]

def getButton(status, pitch, device) :
	if checkStatus(status) == "CONTROL" and device :
		return DEV[device][pitch]
	else :
		return pitch
		
def asDevice(pitch, fromDev, toDev) :
	'''
	Transforms a pitch from fromDev to toDev. Just annoying to do.
	'''
	return DEV_REV[toDev][DEV[fromDev][pitch]]

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
							'interp' : iFunc
	}
