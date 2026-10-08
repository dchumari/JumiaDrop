# SketchUp Automated Importer & SKP Converter
# Instructions:
# 1. Open Trimble SketchUp (Make / Pro).
# 2. Go to: Window -> Ruby Console (or Extensions -> Developer -> Ruby Console)
# 3. Paste the code below and hit Enter:

model = Sketchup.active_model
base_dir = Dir.pwd

# Import Product #01
dae_file_01 = File.join(base_dir, "models_3d", "product_01_nordic_nightstand.dae")
if File.exist?(dae_file_01)
  model.import(dae_file_01, false)
  puts "Successfully imported Product #01 into SketchUp!"
end

# To save as .skp:
# model.save(File.join(base_dir, "models_3d", "product_01_nordic_nightstand.skp"))
