#==============================================================================
# VXA Notetag Parser (original template)
#------------------------------------------------------------------------------
# PURPOSE
#   Reusable notetag parsing for database objects, plus an example that parses
#   <key: value> tags once at database load and caches the results, so game
#   code never re-parses note text during play.
#
#   Example note box text:
#       <vxa_craft_cost: 120>
#       <vxa_rarity: rare>
#   Example use:
#       $data_items[5].vxa_note_int(:craft_cost, 0)   # => 120
#       $data_enemies[3].vxa_note_str(:rarity, "")
#
# INSTALL POSITION
#   Script Editor: below "Materials", above "Main". Place it ABOVE any of your
#   scripts that read notetags. No other script is required.
#
# COMPATIBILITY NOTES
#   - Written for RGSS3 / Ruby 1.9.2 syntax. Host "ruby -c" is diagnostic only;
#     test in actual VX Ace.
#   - Adds methods to RPG::BaseItem and RPG::Enemy. In default VX Ace
#     RPG::Enemy is believed to inherit RPG::BaseItem, so the second include is
#     harmless either way. Verify in your project (UNSURE, hence both).
#   - Only reads the "note" attribute; it never writes to database objects.
#   - Method and constant names carry a VXA_ prefix to avoid collisions.
#
# ALIASES USED
#   DataManager.load_database  ->  vxa_notetag_original_load_database
#   (singleton alias; any other script aliasing the same method is order-
#   dependent but both will run as long as each calls the original.)
#
# SAVE-DATA IMPACT
#   None. The cache lives in instance variables on RPG::* database objects,
#   which are reloaded from Data/*.rvdata2 on every launch and are not part of
#   save files. Existing saves are unaffected; no new game required.
#
# CONFIGURATION
#   VXA_Notetags::TAG_PREFIX   only tags starting with this are cached
#   VXA_Notetags::DATABASES    which $data_* arrays are scanned at load
#==============================================================================

module VXA_Notetags
  # Config -------------------------------------------------------------------
  TAG_PREFIX = "vxa_"
  # Names of the $data_* globals to scan after loading (nil slots skipped).
  DATABASES = [:$data_actors, :$data_classes, :$data_skills, :$data_items,
               :$data_weapons, :$data_armors, :$data_enemies, :$data_states]
  # --------------------------------------------------------------------------

  # <key: value> or <key:value>; key is letters, digits, underscore.
  TAG_REGEXP = /<\s*([A-Za-z0-9_]+)\s*:\s*([^>]*?)\s*>/

  # Returns a Hash { :key => "string value" } for tags in the note text that
  # start with TAG_PREFIX (prefix removed from the key). Later duplicates win.
  def self.parse(note)
    result = {}
    return result if note.nil?
    note.scan(TAG_REGEXP) do |key, value|
      key = key.downcase
      next unless key.index(TAG_PREFIX) == 0
      result[key[TAG_PREFIX.length, key.length].to_sym] = value
    end
    result
  end

  # Iterates every non-nil object in the configured databases.
  def self.each_database_object
    DATABASES.each do |name|
      list = eval(name.to_s)
      next if list.nil?
      list.each { |obj| yield obj unless obj.nil? }
    end
  end

  # Instance methods mixed into RPG::BaseItem / RPG::Enemy.
  module Methods
    # Cached tag hash. Built lazily so objects loaded outside the hook are OK.
    def vxa_notetags
      @vxa_notetags ||= VXA_Notetags.parse(@note)
    end

    def vxa_note_str(key, default = nil)
      value = vxa_notetags[key.to_sym]
      value.nil? ? default : value
    end

    def vxa_note_int(key, default = 0)
      value = vxa_notetags[key.to_sym]
      value.nil? ? default : value.to_i
    end

    def vxa_note_float(key, default = 0.0)
      value = vxa_notetags[key.to_sym]
      value.nil? ? default : value.to_f
    end

    # true for 1/true/yes/on (case-insensitive), false otherwise.
    def vxa_note_flag(key, default = false)
      value = vxa_notetags[key.to_sym]
      return default if value.nil?
      %w(1 true yes on).include?(value.downcase)
    end
  end
end

class RPG::BaseItem
  include VXA_Notetags::Methods
end

class RPG::Enemy
  include VXA_Notetags::Methods
end

class << DataManager
  alias vxa_notetag_original_load_database load_database
  def load_database
    vxa_notetag_original_load_database
    VXA_Notetags.each_database_object { |obj| obj.vxa_notetags }
  end
end
