# Authored RGSS3/Ruby 1.9.2 compile-only scaffold. Generated bundles are PRIVATE.
# Install only in a separate trusted blank disposable host, before Main.
vxace_syntax_rows = [
__VXACE_ROWS__
]
vxace_syntax_available = defined?(RubyVM::InstructionSequence) && RubyVM::InstructionSequence.respond_to?(:compile)
File.open("vxace-native-syntax-__VXACE_TOKEN__.tsv", File::WRONLY | File::CREAT | File::EXCL) do |vxace_syntax_report|
  vxace_syntax_report.write(["VXACE_NATIVE_SYNTAX", "1", "__VXACE_TOKEN__", RUBY_VERSION, (!!vxace_syntax_available).to_s].join("\t") + "\n")
  vxace_syntax_count = 0
  if vxace_syntax_available
    vxace_syntax_rows.each do |vxace_syntax_row|
      vxace_syntax_index, vxace_syntax_digest, vxace_syntax_size, vxace_syntax_hex = vxace_syntax_row
      vxace_syntax_status = "pass"
      vxace_syntax_error = ""
      begin
        vxace_syntax_source = [vxace_syntax_hex].pack("H*")
        raise "Source byte count mismatch" unless vxace_syntax_source.bytesize == vxace_syntax_size
        vxace_syntax_source.force_encoding("UTF-8")
        RubyVM::InstructionSequence.compile(vxace_syntax_source, "VXACE-entry-%04d" % vxace_syntax_index)
      rescue SyntaxError => vxace_syntax_exception
        vxace_syntax_status = "syntax_error"
        vxace_syntax_error = vxace_syntax_exception.message
      rescue StandardError => vxace_syntax_exception
        vxace_syntax_status = "compiler_error"
        vxace_syntax_error = vxace_syntax_exception.message
      end
      vxace_syntax_error = vxace_syntax_error.to_s.dup.force_encoding("ASCII-8BIT")[0, 2048].unpack("H*")[0]
      vxace_syntax_report.write([vxace_syntax_index, vxace_syntax_digest, vxace_syntax_size, vxace_syntax_status, vxace_syntax_error].join("\t") + "\n")
      vxace_syntax_count += 1
    end
  end
  vxace_syntax_report.write("COMPLETE\t" + vxace_syntax_count.to_s + "\n")
end
# Tested scripts are never evaluated. Stop the trusted host before Main runs.
exit
