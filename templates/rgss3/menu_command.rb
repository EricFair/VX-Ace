#==============================================================================
# VXA Menu Command -> Common Event (original template)
#------------------------------------------------------------------------------
# PURPOSE
#   Adds one extra command to the main menu. Choosing it closes the menu and
#   runs a Database common event, so the actual feature (crafting menu,
#   bestiary list, fast travel, ...) stays editable in the event editor.
#
# INSTALL POSITION
#   Script Editor: below "Materials", above "Main". No dependencies.
#
# COMPATIBILITY NOTES
#   - Written for RGSS3 / Ruby 1.9.2 syntax. Host "ruby -c" is diagnostic only;
#     test in actual VX Ace.
#   - Window_MenuCommand#add_original_commands is an empty hook in the default
#     scripts, called between the Formation and Save commands. It is aliased
#     so commands added by other scripts are kept.
#   - Common event reservation uses $game_temp.reserve_common_event, which the
#     default menu item usage relies on; the event starts when the map scene
#     resumes. A common event with a Parallel/Autorun trigger is not needed;
#     use trigger "None".
#   - Command position is set by the hook's place in the default list. Other
#     menu scripts that rebuild the whole command list will ignore this.
#
# ALIASES USED
#   Scene_Menu#create_command_window  ->  vxa_menu_original_create_command_window
#   Window_MenuCommand#add_original_commands
#                                     ->  vxa_menu_original_add_original_commands
#
# SAVE-DATA IMPACT
#   None. Menu windows are transient. Existing saves load normally.
#
# CONFIGURATION (module VXA_MenuCommand)
#   NAME               text shown in the menu
#   COMMON_EVENT_ID    Database common event to run. 0 disables the command.
#                      A project value: create the event and enter its real ID.
#   ENABLE_SWITCH_ID   switch that must be ON to enable the command; 0 means
#                      always enabled. Project value as above.
#==============================================================================

module VXA_MenuCommand
  NAME = "Special"
  COMMON_EVENT_ID = 0
  ENABLE_SWITCH_ID = 0

  def self.active?
    COMMON_EVENT_ID > 0
  end

  def self.enabled?
    return false unless active?
    ENABLE_SWITCH_ID == 0 || $game_switches[ENABLE_SWITCH_ID]
  end
end

class Window_MenuCommand < Window_Command
  # Aliased rather than redefined: the default body is empty, but other
  # scripts commonly add their own commands here.
  alias vxa_menu_original_add_original_commands add_original_commands
  def add_original_commands
    vxa_menu_original_add_original_commands
    if VXA_MenuCommand.active?
      add_command(VXA_MenuCommand::NAME, :vxa_special,
                  VXA_MenuCommand.enabled?)
    end
  end
end

class Scene_Menu < Scene_MenuBase
  alias vxa_menu_original_create_command_window create_command_window
  def create_command_window
    vxa_menu_original_create_command_window
    @command_window.set_handler(:vxa_special, method(:command_vxa_special))
  end

  def command_vxa_special
    $game_temp.reserve_common_event(VXA_MenuCommand::COMMON_EVENT_ID)
    return_scene
  end
end
