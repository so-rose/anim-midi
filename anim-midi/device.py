STATUS_TYPE = {		144 : 'NOTEDOWN',
					128 : 'NOTEUP',
					176 : 'CONTROL',
					224 : 'PITCH_MOD'
}

DEV = {
	"novation_impulse_25" :
		{	49	: 'FADER_1',
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
}

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
