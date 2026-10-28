#==============================================================================
# VXA Map HUD Window (original template)
#------------------------------------------------------------------------------
# PURPOSE
#   A small window on the map showing gold and one game variable (for example
#   a day counter or quest stage). It redraws ONLY when a displayed value
#   changes, so per-frame cost is two comparisons. It is disposed with the map
#   scene, and nothing about it is saved.
#
# INSTALL POSITION
#   Script Editor: below "Materials", above "Main". No dependencies.
#
# COMPATIBILITY NOTES
#   - Written for RGSS3 / Ruby 1.9.2 syntax. Host "ruby -c" is diagnostic only;
#     test in actual VX Ace.
#   - Relies on Scene_Base#dispose_all_windows and #update_all_windows acting
#     on every Window held in an instance variable of the scene. This is the
#     behavior of the default scripts as far as the author recalls; if your
#     project replaced Scene_Base/Scene_Map, check it (UNSURE for modified
#     projects) or dispose/update @vxa_hud_window yourself.
#   - Scripts that also alias Scene_Map#create_all_windows stack safely if each
#     calls the original.
#
# ALIASES USED
#   Scene_Map#create_all_windows  ->  vxa_hud_original_create_all_windows
#
# SAVE-DATA IMPACT
#   None. The window is transient scene state and is rebuilt every time the map
#   scene starts. Existing saves load normally; no new game required.
#
# CONFIGURATION (module VXA_Hud)
#   X, Y, WIDTH            window placement/size (pixels)
#   VARIABLE_ID            variable to display; 0 disables that line
#   VARIABLE_LABEL         text shown before the variable value
#   GOLD_LABEL             text shown after the gold amount
#   SHOW_SWITCH_ID         switch that must be ON for the HUD to show; 0 means
#                          always shown. The ID is a project value: set it to
#                          a real switch you created, never a guessed number.
#==============================================================================

module VXA_Hud
  X = 0
  Y = 0
  WIDTH = 200
  VARIABLE_ID = 0
  VARIABLE_LABEL = "Day"
  GOLD_LABEL = "G"
  SHOW_SWITCH_ID = 0
end

class Window_VXAHud < Window_Base
  def initialize
    lines = (VXA_Hud::VARIABLE_ID > 0) ? 2 : 1
    super(VXA_Hud::X, VXA_Hud::Y, VXA_Hud::WIDTH, fitting_height(lines))
    @shown_gold = nil
    @shown_variable = nil
    self.opacity = 160
    refresh
    update_visibility
  end

  def update
    super
    update_visibility
    refresh if value_changed?
  end

  def value_changed?
    return true if @shown_gold != $game_party.gold
    return true if VXA_Hud::VARIABLE_ID > 0 &&
                   @shown_variable != $game_variables[VXA_Hud::VARIABLE_ID]
    false
  end

  def update_visibility
    id = VXA_Hud::SHOW_SWITCH_ID
    self.visible = (id == 0) || $game_switches[id]
  end

  def refresh
    contents.clear
    @shown_gold = $game_party.gold
    draw_text(0, 0, contents_width, line_height,
              @shown_gold.to_s + " " + VXA_Hud::GOLD_LABEL, 2)
    if VXA_Hud::VARIABLE_ID > 0
      @shown_variable = $game_variables[VXA_Hud::VARIABLE_ID]
      draw_text(0, line_height, contents_width, line_height,
                VXA_Hud::VARIABLE_LABEL + " " + @shown_variable.to_s, 2)
    end
  end
end

class Scene_Map < Scene_Base
  alias vxa_hud_original_create_all_windows create_all_windows
  def create_all_windows
    vxa_hud_original_create_all_windows
    @vxa_hud_window = Window_VXAHud.new
  end
end
