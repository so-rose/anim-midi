bl_info = { 
	"name"      : "Animate MIDI", 
	"category"  : "Scene",
	"author"    : "Sofus Rose",
	"version"   : (0, 7),
	"blender"   : (2, 78, 0),
	"location"  : "Panel > Scene",
}
 
# To support reload properly, try to access a package var, 
# if it's there, reload everything
if "bpy" in locals():
	import imp
	imp.reload(midi_interface)
	imp.reload(device)
	print("Imported all files.")
else:
	from . import midi_interface
	from . import device
	
	STATUS_MAP = device.STATUS_MAP
	DEV = device.DEV
	anim_bind = device.anim_bind
	
	print("Imported all files.")
 
import bpy
from bpy.props import *


#Constants
FPS = 60 #Set for smoothness vs. Performance.
SAMPLE_FAC = 3 #The number of times per frame that the MIDI controls are sampled.

#Queues
q = mp.Queue() #For the JACK process to send data to Blender.
cmdQ = mp.Queue() #To send commands to the JACK process.

#The current mutable settings. They have to be mutable, so that they can be edited on runtime.
BLEND_MAP = {}
CUR_DEV = ""
ACTIVE = False

#Start/Stop Operator
class StartMIDI(bpy.types.Operator) :
	bl_idname = 'amidi.toggle'
	bl_label = 'Toggles the status of Jack, and the Modal.'
	
	def execute(self, context) :
		#~ global ACTIVE, q, cmdQ
		
		if ACTIVE :
			#Unregister modal and stop jack.
			cmdQ.put('QUIT')
			bpy.utils.unregister_class(ModalTimerOperator)
			
			self.report({'INFO'}, 'Stopped Jack & Modal')
		else :
			try :
				CUR_DEV = DEV[context.scene.amidi.device]
			except :
				self.report({'INFO'}, 'Device does not exist!')
			
			proc = mp.Process(target=midi_interface.jack_proc, args=(q, cmdQ, copy.deepcopy(STATUS_TYPE)))
			proc.start()
			
			self.report({'INFO'}, 'Started Jack & Modal')
		return {'FINISHED'}

#Bind new property operator.
class BindProp(bpy.types.Operator) :
	bl_idname = 'amidi.bind'
	bl_label = 'Binds the new property operator.'
	
	def execute(self, context) :
		anim_bind(*list(context.scene.amidi.bProp), iRange=context.scene.amidi.iRange, oRange=context.scene.amidi.oRange, iFunc=context.scene.amidi.iFunc)
		
		return {'FINISHED'}

class ScenePanel(bpy.types.Panel) :
	bl_label = "LineMarch Options"
	bl_idname = "OBJECT_PT_anmidiscn"

	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	bl_context = "scene"
	
	def draw(self, context):
		global ACTIVE
		
		layout = self.layout
		split = layout.split()
		
		col1 = split.column()
		
		row1 = layout.row()
		
		if ACTIVE:
			row1.operator('amid.toggle', text="Stop MIDI")
		else :
			row1.operator('amid.toggle', text="Start MIDI")
			
		row2 = layout.row()
		row2.prop(context.scene.amidi, "device")
		row2.label(text="Supported Devices")
		
		box = row2.box()
		
		for key in DEV :
			box.label(text=key)
			
		layout.label(text="Bind Property Options")
		
		row3 = layout.row()
		row3.prop(context.scene.amidi, "bProp")
		row3.prop(context.scene.amidi, "Device")
		
		row4 = layout.row()
		row4.prop(context.scene.amidi, "iRange")
		row4.prop(context.scene.amidi, "oRange")
		
		row5 = layout.row()
		row5.prop(context.scene.amidi, "iFunc")
		
		row6 = layout.row()
		row6.operator('amidi.bind', text="Bind Prop")
		
class PropList(bpy.types.PropertyGroup) :
	name = bpy.props.StringProperty(name="Blender Property", default="bProp")
	value = bpy.props.StringProperty(name="Property Value", default="")
		
class SceneProperties(bpy.types.PropertyGroup) :
	@classmethod
	def register(cls):
		bpy.types.Scene.amidi = PointerProperty(
			name="Custom Props",
			description="Custom Properties for the anim-midi addon.",
			type=cls,
		)
		
		cls.device = StringProperty(
			name="Device",
			default="novation_impulse_25",
			description="The device map to use. Changed when the program is toggled."
		)
		
		#~ cls.bProp = StringProperty(
			#~ name="Property",
			#~ default="",
			#~ description="The Blender property to bind to this button."
		#~ )
		
		cls.bProp = CollectionProperty(
			type = PropList
		)
		
		cls.list_index = IntProperty(
			name="Index for bProp",
			default=0
		)
		
		cls.iFunc = StringProperty(
			name="Interp Func",
			default="x",
			description="Given (0..1) MIDI input x, the above must evaluate to a (0..1) MIDI output y."
		)
		
		cls.iRange = FloatVectorProperty(
			name="Input Range",
			size = 2,
			default=(0,127),
			min=0,
			description="The raw MIDI input range."
		)
		
		cls.oRange = FloatVectorProperty(
			name="Output Range",
			size = 2,
			default=(0.0,1.0),
			description="The Blender output range."
		)

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
			#Do cool things.
			try:
				#Dequeue all new signal data.
				newItems = []
				while not q.empty() :
					newItems.append(q.get(block=False))
				
				#Only use the last - newest - item in the dequeue'd list.
				# --> We get smoothness by ignoring most of the data!
				item = newItems[-1]
			except :
				return {'PASS_THROUGH'}
				
			try :
				bind = BLEND_MAP[CUR_DEV[item[1]]]
			except :
				print('Button not bound! MIDI channel #:', item[1])
				return {'PASS_THROUGH'}
				
			
			val_nrm = scaleRange(item[2], bind['input_range'], (0, 1))
			val_interp = bind['interp'](val_nrm) #Call the attached interpolation function on the normalized value.
			bVal = scaleRange(val_interp, (0, 1), bind['output_range'])
			
			
			if CHAN_MAP[item[1]] == bind['button'] :
				for bProp in bind['blender_prop'] :
					exec("{0} = {1}".format(bProp, bVal))
					
			
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
		cmdQ.put('QUIT')
		print("Quit anim-midi.")

#Register All
 
def register():
	bpy.utils.register_module(__name__)
 
def unregister():
	bpy.utils.unregister_module(__name__)
 
if __name__ == "__main__":
	register()
