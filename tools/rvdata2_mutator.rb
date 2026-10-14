#!/usr/bin/env ruby
# frozen_string_literal: true
# Copy-only RPG Maker VX Ace Marshal mutator for verified staging workflows.
require 'json'
require 'zlib'
require 'fileutils'
require 'base64'
require 'digest'

module VXACEMutator
  VERSION = '0.8.0'
  module_function

  def define_class(path)
    current = Object
    path.split('::').each_with_index do |part, index|
      if current.const_defined?(part, false)
        current = current.const_get(part, false)
      else
        value = (index == 0 && part == 'RPG') ? Module.new : Class.new
        current.const_set(part, value)
        current = value
      end
    end
    current
  end

  def json_value(value)
    case value
    when Array then value.map { |x| json_value(x) }
    when Hash then value.each_with_object({}) { |(k,v),h| h[k] = json_value(v) }
    else value
    end
  end

  class Encoder
    def initialize
      @seen = {}
      @next_id = 1
    end
    def encode(value)
      case value
      when NilClass, TrueClass, FalseClass, Integer, Float then value
      when Symbol then {'__symbol__'=>value.to_s}
      when String
        begin
          text = value.encode('UTF-8')
          {'__string__'=>text}
        rescue StandardError
          {'__binary__'=>Base64.strict_encode64(value.b)}
        end
      when Array then encode_array(value)
      when Hash then encode_hash(value)
      when Table then encode_special(value, %i[dimensions xsize ysize zsize data])
      when Color then encode_special(value, %i[red green blue alpha])
      when Tone then encode_special(value, %i[red green blue gray])
      when Rect then {'__class__'=>'Rect','raw_base64'=>Base64.strict_encode64(value.raw_payload || ''.b)}
      else encode_object(value)
      end
    end
    def ref(value)
      oid=value.object_id
      return {'__ref__'=>@seen[oid]} if @seen.key?(oid)
      id=@next_id; @next_id+=1; @seen[oid]=id; id
    end
    def encode_array(value)
      id=ref(value); return id if id.is_a?(Hash)
      {'__id__'=>id,'__array__'=>value.map{|x|encode(x)}}
    end
    def encode_hash(value)
      id=ref(value); return id if id.is_a?(Hash)
      pairs=value.map{|k,v|[encode(k),encode(v)]}
      {'__id__'=>id,'__hash__'=>pairs}
    end
    def encode_special(value, attrs)
      id=ref(value); return id if id.is_a?(Hash)
      out={'__id__'=>id,'__class__'=>value.class.name}
      attrs.each{|a| out[a.to_s]=encode(value.public_send(a))}
      out
    end
    def encode_object(value)
      id=ref(value); return id if id.is_a?(Hash)
      out={'__id__'=>id,'__class__'=>value.class.name.to_s}
      value.instance_variables.sort_by(&:to_s).each do |ivar|
        out[ivar.to_s.sub(/^@/,'')]=encode(value.instance_variable_get(ivar))
      end
      out
    end
  end

  def inspect_marshaled(path)
    encoded = Encoder.new.encode(load_marshaled(path))
    json = JSON.generate(encoded)
    {'semantic_sha256'=>Digest::SHA256.hexdigest(json), 'data'=>encoded}
  end
  def load_marshaled(path)
    File.open(path, 'rb') { |f| Marshal.load(f) }
  end

  def write_marshaled(value, path)
    FileUtils.mkdir_p(File.dirname(path))
    tmp = path + '.tmp'
    File.open(tmp, 'wb') { |f| Marshal.dump(value, f) }
    File.rename(tmp, path)
  ensure
    File.delete(tmp) if defined?(tmp) && File.exist?(tmp)
  end

  def object_by_id(root, id)
    unless root.is_a?(Array)
      raise "database root is #{root.class}, expected Array for id lookup"
    end
    root.find do |obj|
      next false unless obj && obj.respond_to?(:instance_variable_get)
      obj.instance_variable_get(:@id).to_i == id.to_i
    end
  end

  def apply_database(root, mutation)
    id = Integer(mutation.fetch('id'))
    field = mutation.fetch('field').to_s
    raise 'unsafe field name' unless field.match?(/\A[a-zA-Z_][a-zA-Z0-9_]*\z/)
    obj = object_by_id(root, id) or raise "database object id #{id} not found"
    ivar = "@#{field}".to_sym
    raise "database field #{field} does not already exist on object id #{id}" unless obj.instance_variable_defined?(ivar)
    obj.instance_variable_set(ivar, json_value(mutation['value']))
  end

  def fetch_map_event(root, mutation)
    events = root.instance_variable_get(:@events)
    raise 'map has no @events hash' unless events.is_a?(Hash)
    event_id = Integer(mutation.fetch('event_id'))
    event = events[event_id] or raise "event id #{event_id} not found"
    pages = event.instance_variable_get(:@pages)
    page_number = Integer(mutation.fetch('page'))
    page = pages && pages[page_number - 1] or raise "event page #{page_number} not found"
    [event, page]
  end

  def fetch_troop_page(root, mutation)
    troop_id = Integer(mutation.fetch('troop_id'))
    troop = object_by_id(root, troop_id) or raise "troop id #{troop_id} not found"
    pages = troop.instance_variable_get(:@pages)
    page_number = Integer(mutation.fetch('page'))
    page = pages && pages[page_number - 1] or raise "troop page #{page_number} not found"
    [troop, page]
  end

  def fetch_common_event(root, mutation)
    id = Integer(mutation.fetch('common_event_id'))
    event = object_by_id(root, id) or raise "common event id #{id} not found"
    [event, event]
  end

  def apply_event(root, mutation)
    _owner, holder = case mutation.fetch('scope')
                     when 'map' then fetch_map_event(root, mutation)
                     when 'troop' then fetch_troop_page(root, mutation)
                     when 'common_event' then fetch_common_event(root, mutation)
                     else raise "unsupported event scope: #{mutation['scope']}"
                     end
    list = holder.instance_variable_get(:@list)
    raise 'target has no @list event command array' unless list.is_a?(Array)
    index = Integer(mutation.fetch('command_index'))
    command = list[index] or raise "command index #{index} not found"
    case mutation.fetch('action')
    when 'set_parameters'
      value = mutation.fetch('parameters')
      raise 'parameters must be an Array' unless value.is_a?(Array)
      command.instance_variable_set(:@parameters, json_value(value))
    when 'set_parameter'
      params = command.instance_variable_get(:@parameters)
      raise 'command @parameters is not an Array' unless params.is_a?(Array)
      pindex = Integer(mutation.fetch('parameter_index'))
      raise "parameter index #{pindex} out of range" if pindex < 0 || pindex >= params.length
      params[pindex] = json_value(mutation['value'])
    else
      raise "unsupported event action: #{mutation['action']}"
    end
  end

  def apply_scripts(root, mutation)
    raise "scripts root is #{root.class}, expected Array" unless root.is_a?(Array)
    index = Integer(mutation.fetch('script_index'))
    entry = root[index] or raise "script index #{index} not found"
    raise 'invalid script archive entry' unless entry.is_a?(Array) && entry.length >= 3
    source = Zlib::Inflate.inflate(entry[2])
    search = mutation.fetch('search').to_s
    replacement = mutation.fetch('replace').to_s
    count = source.scan(Regexp.new(Regexp.escape(search))).length
    raise "search block must occur exactly once; found #{count}" unless count == 1
    source = source.sub(search, replacement)
    entry[2] = Zlib::Deflate.deflate(source)
  end

  def mutate(input, output, spec_path)
    input = File.expand_path(input)
    output = File.expand_path(output)
    raise 'input and output must differ' if input == output
    spec = JSON.parse(File.read(spec_path, encoding: 'UTF-8'))
    root = load_marshaled(input)
    type = spec.fetch('type')
    mutation = spec.fetch('mutation')
    case type
    when 'database' then apply_database(root, mutation)
    when 'event' then apply_event(root, mutation)
    when 'scripts' then apply_scripts(root, mutation)
    else raise "unsupported mutation type: #{type}"
    end
    write_marshaled(root, output)
  end

  def roundtrip(input, output)
    write_marshaled(load_marshaled(input), File.expand_path(output))
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
  def _dump(_limit)
    [@dimensions, @xsize, @ysize, @zsize, @data.length, *@data].pack('V5v*')
  end
end
class Color
  attr_reader :red, :green, :blue, :alpha
  def self._load(payload); v=payload.unpack('E4'); o=allocate; %i[red green blue alpha].each_with_index{|n,i|o.instance_variable_set("@#{n}",v[i]||0.0)}; o; end
  def _dump(_limit); [@red,@green,@blue,@alpha].pack('E4'); end
end
class Tone
  attr_reader :red, :green, :blue, :gray
  def self._load(payload); v=payload.unpack('E4'); o=allocate; %i[red green blue gray].each_with_index{|n,i|o.instance_variable_set("@#{n}",v[i]||0.0)}; o; end
  def _dump(_limit); [@red,@green,@blue,@gray].pack('E4'); end
end
class Rect
  attr_reader :raw_payload
  def self._load(payload); o=allocate; o.instance_variable_set(:@raw_payload,payload); o; end
  def _dump(_limit); @raw_payload || ''.b; end
end
module RPG; end
[
'RPG::BaseItem','RPG::BaseItem::Feature','RPG::UsableItem','RPG::UsableItem::Damage','RPG::UsableItem::Effect','RPG::EquipItem','RPG::Actor','RPG::Class','RPG::Class::Learning','RPG::Skill','RPG::Item','RPG::Weapon','RPG::Armor','RPG::Enemy','RPG::Enemy::DropItem','RPG::Enemy::Action','RPG::State','RPG::Animation','RPG::Animation::Frame','RPG::Animation::Timing','RPG::Tileset','RPG::CommonEvent','RPG::System','RPG::System::Vehicle','RPG::System::Terms','RPG::System::TestBattler','RPG::Map','RPG::Map::Encounter','RPG::MapInfo','RPG::Event','RPG::Event::Page','RPG::Event::Page::Condition','RPG::Event::Page::Graphic','RPG::EventCommand','RPG::MoveRoute','RPG::MoveCommand','RPG::Troop','RPG::Troop::Member','RPG::Troop::Page','RPG::Troop::Page::Condition','RPG::AudioFile','RPG::BGM','RPG::BGS','RPG::ME','RPG::SE'
].each { |name| VXACEMutator.define_class(name) }
class Module
  unless method_defined?(:vxace_mutator_original_const_missing)
    alias vxace_mutator_original_const_missing const_missing
  end
  def const_missing(name); const_set(name, Class.new); end
end

mode = ARGV[0]
valid = (mode == 'roundtrip' && ARGV.length == 3) || (mode == 'mutate' && ARGV.length == 4) || (mode == 'inspect' && ARGV.length == 2)
unless valid
  warn 'Usage: ruby rvdata2_mutator.rb roundtrip INPUT OUTPUT'
  warn '   or: ruby rvdata2_mutator.rb mutate INPUT OUTPUT SPEC'
  warn '   or: ruby rvdata2_mutator.rb inspect INPUT'
  exit 2
end
begin
  if mode == 'roundtrip'
    VXACEMutator.roundtrip(ARGV[1], ARGV[2])
    puts JSON.generate({'status'=>'ok','mode'=>mode,'version'=>VXACEMutator::VERSION})
  elsif mode == 'mutate'
    VXACEMutator.mutate(ARGV[1], ARGV[2], ARGV[3])
    puts JSON.generate({'status'=>'ok','mode'=>mode,'version'=>VXACEMutator::VERSION})
  else
    puts JSON.generate(VXACEMutator.inspect_marshaled(ARGV[1]).merge('status'=>'ok','mode'=>'inspect','version'=>VXACEMutator::VERSION))
  end
rescue StandardError => e
  warn "VX Ace mutator error: #{e.class}: #{e.message}"
  exit 1
end
