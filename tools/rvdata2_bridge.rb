#!/usr/bin/env ruby
# frozen_string_literal: true

# Read-only Ruby Marshal bridge for RPG Maker VX Ace .rvdata2 files.
#
# This helper exists to let the Python project reader inspect Marshal 4.8 data
# without executing project scripts. It defines inert stand-ins for RGSS/RPG
# classes, then serializes loaded data to normalized JSON.
#
# It never writes to the source project.

require 'json'
require 'zlib'
require 'base64'
require 'digest'

module VXACEBridge
  VERSION = '0.21.0'

  def self.safe_string(value)
    s = value.to_s
    begin
      s.encode('UTF-8', invalid: :replace, undef: :replace, replace: '\uFFFD')
    rescue StandardError
      s.force_encoding('BINARY').encode('UTF-8', invalid: :replace, undef: :replace, replace: '\uFFFD')
    end
  end
end

class Table
  attr_reader :dimensions, :xsize, :ysize, :zsize, :data
  def self._load(payload)
    values = payload.unpack('V5v*'); obj = allocate
    obj.instance_variable_set(:@dimensions, values[0] || 0)
    obj.instance_variable_set(:@xsize, values[1] || 0)
    obj.instance_variable_set(:@ysize, values[2] || 0)
    obj.instance_variable_set(:@zsize, values[3] || 0)
    count = values[4] || 0
    obj.instance_variable_set(:@data, values[5, count] || [])
    obj
  end
end

class Color
  attr_reader :red, :green, :blue, :alpha
  def self._load(payload)
    values = payload.unpack('E4'); obj = allocate
    obj.instance_variable_set(:@red, values[0] || 0.0); obj.instance_variable_set(:@green, values[1] || 0.0)
    obj.instance_variable_set(:@blue, values[2] || 0.0); obj.instance_variable_set(:@alpha, values[3] || 0.0); obj
  end
end

class Tone
  attr_reader :red, :green, :blue, :gray
  def self._load(payload)
    values = payload.unpack('E4'); obj = allocate
    obj.instance_variable_set(:@red, values[0] || 0.0); obj.instance_variable_set(:@green, values[1] || 0.0)
    obj.instance_variable_set(:@blue, values[2] || 0.0); obj.instance_variable_set(:@gray, values[3] || 0.0); obj
  end
end

class Rect
  attr_reader :raw_payload
  def self._load(payload); obj = allocate; obj.instance_variable_set(:@raw_payload, payload); obj; end
end

module RPG; end

def vxace_bridge_define_class(path)
  current = Object
  path.split('::').each_with_index do |part, index|
    if current.const_defined?(part, false)
      current = current.const_get(part, false)
    else
      value = (index == 0 && part == 'RPG') ? Module.new : Class.new
      current.const_set(part, value); current = value
    end
  end
  current
end

[
  'RPG::BaseItem', 'RPG::BaseItem::Feature', 'RPG::UsableItem', 'RPG::UsableItem::Damage', 'RPG::UsableItem::Effect',
  'RPG::EquipItem', 'RPG::Actor', 'RPG::Class', 'RPG::Class::Learning', 'RPG::Skill', 'RPG::Item', 'RPG::Weapon', 'RPG::Armor',
  'RPG::Enemy', 'RPG::Enemy::DropItem', 'RPG::Enemy::Action', 'RPG::State', 'RPG::Animation', 'RPG::Animation::Frame', 'RPG::Animation::Timing',
  'RPG::Tileset', 'RPG::CommonEvent', 'RPG::System', 'RPG::System::Vehicle', 'RPG::System::Terms', 'RPG::System::TestBattler',
  'RPG::Map', 'RPG::Map::Encounter', 'RPG::MapInfo', 'RPG::Event', 'RPG::Event::Page', 'RPG::Event::Page::Condition', 'RPG::Event::Page::Graphic',
  'RPG::EventCommand', 'RPG::MoveRoute', 'RPG::MoveCommand', 'RPG::Troop', 'RPG::Troop::Member', 'RPG::Troop::Page', 'RPG::Troop::Page::Condition',
  'RPG::AudioFile', 'RPG::BGM', 'RPG::BGS', 'RPG::ME', 'RPG::SE'
].each { |name| vxace_bridge_define_class(name) }

class Module
  unless method_defined?(:vxace_bridge_original_const_missing)
    alias vxace_bridge_original_const_missing const_missing
  end
  def const_missing(name); const_set(name, Class.new); end
end

module VXACEBridge
  class Encoder
    def initialize; @seen = {}; @next_id = 1; end
    def encode(value)
      case value
      when NilClass, TrueClass, FalseClass, Integer, Float then value
      when Symbol then { '__symbol__' => value.to_s }
      when String then VXACEBridge.safe_string(value)
      when Array then encode_array(value)
      when Hash then encode_hash(value)
      when Table then encode_table(value)
      when Color then encode_rgss_value(value, %w[red green blue alpha])
      when Tone then encode_rgss_value(value, %w[red green blue gray])
      when Rect then { '__class__' => 'Rect', 'raw_base64' => Base64.strict_encode64(value.raw_payload || ''.b) }
      else encode_object(value)
      end
    end
    private
    def reference_for(value)
      oid = value.object_id; return { '__ref__' => @seen[oid] } if @seen.key?(oid)
      ident = @next_id; @next_id += 1; @seen[oid] = ident; ident
    end
    def encode_array(value); ref = reference_for(value); return ref if ref.is_a?(Hash); { '__id__' => ref, '__array__' => value.map { |i| encode(i) } }; end
    def encode_hash(value); ref = reference_for(value); return ref if ref.is_a?(Hash); { '__id__' => ref, '__hash__' => value.map { |k,v| [encode(k), encode(v)] } }; end
    def encode_table(value)
      ref = reference_for(value); return ref if ref.is_a?(Hash)
      { '__id__'=>ref, '__class__'=>'Table', 'dimensions'=>value.dimensions, 'xsize'=>value.xsize, 'ysize'=>value.ysize, 'zsize'=>value.zsize, 'data'=>value.data }
    end
    def encode_rgss_value(value, attrs)
      ref = reference_for(value); return ref if ref.is_a?(Hash); result = { '__id__'=>ref, '__class__'=>value.class.name }
      attrs.each { |name| result[name] = value.public_send(name) }; result
    end
    def encode_object(value)
      ref = reference_for(value); return ref if ref.is_a?(Hash); result = { '__id__'=>ref, '__class__'=>value.class.name.to_s }
      value.instance_variables.sort_by(&:to_s).each { |ivar| result[ivar.to_s.sub(/^@/,'')] = encode(value.instance_variable_get(ivar)) }; result
    end
  end

  def self.load_marshaled(path); File.open(path, 'rb') { |file| Marshal.load(file) }; end
  def self.dump_json(path); puts JSON.pretty_generate(Encoder.new.encode(load_marshaled(path))); end
  def self.dump_scripts(path)
    data = load_marshaled(path); raise "Scripts archive root is #{data.class}, expected Array" unless data.is_a?(Array)
    raise 'Script count budget exceeded' if data.length > 4096
    total_source_bytes = 0
    scripts = data.each_with_index.map do |entry,index|
      raise "Invalid script archive entry #{index}" unless entry.is_a?(Array) && entry.length >= 3
      id,name,compressed = entry[0],entry[1],entry[2]
      raise "Invalid compressed script #{index}" unless compressed.is_a?(String) && compressed.bytesize <= 16 * 1024 * 1024
      inflater = Zlib::Inflate.new
      source = ''.b
      begin
        offset = 0
        while offset < compressed.bytesize
          piece = inflater.inflate(compressed.byteslice(offset, 32768))
          raise "Script #{index} source byte budget exceeded" if source.bytesize + piece.bytesize > 16 * 1024 * 1024
          source << piece
          offset += 32768
        end
        raise "Incomplete or trailing compressed script #{index}" unless inflater.finished? && inflater.total_in == compressed.bytesize
      ensure
        inflater.close
      end
      total_source_bytes += source.bytesize
      raise 'Total script source byte budget exceeded' if total_source_bytes > 64 * 1024 * 1024
      utf8 = source.dup.force_encoding('UTF-8')
      raise "Script #{index} is not valid UTF-8; code-page review required" unless utf8.valid_encoding?
      crlf = source.scan(/\r\n/).length
      { 'index'=>index, 'id'=>id, 'name'=>safe_string(name), 'source'=>utf8,
        'source_sha256'=>Digest::SHA256.hexdigest(source), 'source_bytes'=>source.bytesize,
        'utf8_decodable'=>true, 'ascii_only'=>utf8.ascii_only?,
        'newlines'=>{ 'crlf'=>crlf, 'bare_lf'=>source.count("\n")-crlf, 'bare_cr'=>source.count("\r")-crlf } }
    end
    puts JSON.pretty_generate({ 'bridge_version'=>VERSION, 'scripts'=>scripts })
  end
end

if ARGV.length != 2 || !%w[dump scripts].include?(ARGV[0]); warn "Usage: ruby rvdata2_bridge.rb <dump|scripts> PATH"; exit 2; end
mode = ARGV[0]; path = File.expand_path(ARGV[1]); unless File.file?(path); warn "File not found: #{path}"; exit 2; end
begin
  mode == 'scripts' ? VXACEBridge.dump_scripts(path) : VXACEBridge.dump_json(path)
rescue StandardError => e
  warn "VX Ace bridge error: #{e.class}: #{e.message}"; warn e.backtrace.join("\n") if ENV['VXACE_BRIDGE_DEBUG'] == '1'; exit 1
end
