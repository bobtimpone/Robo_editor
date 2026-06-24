import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import json
import urllib.request

from editor_engine import EditorEngine
from agents import EditorAgent, create_agents, AgentOrchestrator

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
CONFIG_FILE = "robo_config.json"

class RoboEditorUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Robo-Editor: AI Manuscript Assistant")
        self.geometry("850x950") 
        self.grid_columnconfigure(0, weight=1)
        
        self.engine = EditorEngine(ollama_url="http://localhost:11434")
        self.is_processing = False
        
        self.setup_variables()
        self.setup_ui()
        self.load_config()
        self.fetch_models()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_variables(self):
        self.input_var = ctk.StringVar()
        self.output_var = ctk.StringVar()
        self.model_var = ctk.StringVar()
        
        self.chunk_size_var = ctk.StringVar(value="1500")
        self.context_size_var = ctk.StringVar(value="8192")
        
        self.genre_var = ctk.StringVar(value="Sci-Fi")
        self.voice_var = ctk.StringVar(value="None")
        self.tempo_var = ctk.StringVar(value="None")
        
        self.fast_mode_var = ctk.BooleanVar(value=False)
        self.autofix_var = ctk.BooleanVar(value=True)
        
        self.edit_vars = {
            "Developmental Edit": ctk.BooleanVar(value=True),
            "Line Edit": ctk.BooleanVar(value=True),
            "Copy Edit": ctk.BooleanVar(value=True),
            "Proofread": ctk.BooleanVar(value=True),
            "Humanize Pass": ctk.BooleanVar(value=False)
        }

    def setup_ui(self):
        # --- File Settings ---
        file_frame = ctk.CTkFrame(self)
        file_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        file_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(file_frame, text="File Settings", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkLabel(file_frame, text="Input (.docx):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkEntry(file_frame, textvariable=self.input_var).grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(file_frame, text="Browse...", width=100, command=self.browse_input).grid(row=1, column=2, padx=10, pady=5)
        
        ctk.CTkLabel(file_frame, text="Output (.docx):").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkEntry(file_frame, textvariable=self.output_var).grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(file_frame, text="Browse...", width=100, command=self.browse_output).grid(row=2, column=2, padx=10, pady=5)

        # --- Ollama Settings ---
        model_frame = ctk.CTkFrame(self)
        model_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        model_frame.grid_columnconfigure(1, weight=1)
        model_frame.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(model_frame, text="Engine Settings", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkLabel(model_frame, text="Select Model:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.model_dropdown = ctk.CTkOptionMenu(model_frame, variable=self.model_var, values=["Loading..."])
        self.model_dropdown.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(model_frame, text="Refresh", width=80, command=self.fetch_models).grid(row=1, column=2, padx=10, pady=5)
        
        ctk.CTkLabel(model_frame, text="Max Tokens/Chunk:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkOptionMenu(model_frame, variable=self.chunk_size_var, values=["500", "1000", "1500", "2000"]).grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(model_frame, text="Context Limit:").grid(row=2, column=2, padx=10, pady=5, sticky="w")
        ctk.CTkOptionMenu(model_frame, variable=self.context_size_var, values=["4096", "8192", "16384", "32768", "65536"]).grid(row=2, column=3, padx=10, pady=5, sticky="ew")

        # --- Global Context & Style ---
        style_frame = ctk.CTkFrame(self)
        style_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        for i in range(1, 6, 2): style_frame.grid_columnconfigure(i, weight=1)
        
        context_header_frame = ctk.CTkFrame(style_frame, fg_color="transparent")
        context_header_frame.grid(row=0, column=0, columnspan=6, sticky="ew")
        
        ctk.CTkLabel(context_header_frame, text="Global Continuity Master", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10, pady=10)
        self.generate_specs_btn = ctk.CTkButton(context_header_frame, text="🧠 Auto-Extract Story Bible", width=180, fg_color="#8e44ad", hover_color="#9b59b6", command=self.start_specs_generation)
        self.generate_specs_btn.pack(side="right", padx=10, pady=5)
        
        self.global_context_box = ctk.CTkTextbox(style_frame, height=120)
        self.global_context_box.grid(row=1, column=0, columnspan=6, padx=10, pady=(0, 10), sticky="ew")
        self.global_context_box.insert("1.0", "Auto-generate or enter character descriptions, lore, and plot rules here so the downstream editing agents remember the big picture...")
        
        ctk.CTkLabel(style_frame, text="Format:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkOptionMenu(style_frame, variable=self.genre_var, values=["Sci-Fi", "Fantasy", "Thriller", "Technical Manual", "None"]).grid(row=2, column=1, padx=(0,10), pady=5, sticky="ew")
        ctk.CTkLabel(style_frame, text="Voice:").grid(row=2, column=2, padx=10, pady=5, sticky="w")
        ctk.CTkOptionMenu(style_frame, variable=self.voice_var, values=["Gritty", "Conversational", "Authoritative", "None"]).grid(row=2, column=3, padx=(0,10), pady=5, sticky="ew")
        ctk.CTkLabel(style_frame, text="Pacing:").grid(row=2, column=4, padx=10, pady=5, sticky="w")
        ctk.CTkOptionMenu(style_frame, variable=self.tempo_var, values=["Balanced", "Fast", "Slow", "None"]).grid(row=2, column=5, padx=(0,10), pady=5, sticky="ew")

        # --- Pipeline Settings ---
        pipe_frame = ctk.CTkFrame(self)
        pipe_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(pipe_frame, text="Agent Roster", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        stages_frame = ctk.CTkFrame(pipe_frame, fg_color="transparent")
        stages_frame.grid(row=1, column=0, columnspan=4, padx=10, sticky="w")
        for i, (name, var) in enumerate(self.edit_vars.items()):
            ctk.CTkCheckBox(stages_frame, text=name, variable=var).grid(row=0, column=i, padx=(0, 15), pady=5)
            
        ctk.CTkSwitch(pipe_frame, text="⚡ Fast Mode: Combine agents into a single pass", variable=self.fast_mode_var, progress_color="#d35400").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkSwitch(pipe_frame, text="🛠 Auto-Fix Exceptions: Downstream agents actively resolve logic issues", variable=self.autofix_var, progress_color="#2980b9").grid(row=3, column=0, padx=10, pady=(0, 10), sticky="w")

        # --- Controls & Progress ---
        control_frame = ctk.CTkFrame(self, fg_color="transparent")
        control_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        
        self.start_btn = ctk.CTkButton(control_frame, text="Start Editing Process", fg_color="#2ecc71", hover_color="#27ae60", font=ctk.CTkFont(weight="bold"), command=self.start_process)
        self.start_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.stop_btn = ctk.CTkButton(control_frame, text="Stop/Cancel", fg_color="#e74c3c", hover_color="#c0392b", font=ctk.CTkFont(weight="bold"), state="disabled", command=self.stop_process)
        self.stop_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(self, text="Ready.", text_color="gray")
        self.status_label.grid(row=6, column=0, padx=20, sticky="w")
        
        # --- Log ---
        self.log_area = ctk.CTkTextbox(self, height=120)
        self.log_area.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.grid_rowconfigure(7, weight=1)

    # --- STATE PERSISTENCE ---
    def save_config(self):
        context_text = self.global_context_box.get("1.0", "end-1c").strip()
        if context_text.startswith("Auto-generate or enter"): context_text = ""
        
        config = {
            "chunk_size": self.chunk_size_var.get(),
            "context_size": self.context_size_var.get(),
            "genre": self.genre_var.get(),
            "voice": self.voice_var.get(),
            "tempo": self.tempo_var.get(),
            "fast_mode": self.fast_mode_var.get(),
            "auto_fix": self.autofix_var.get(),
            "model": self.model_var.get(),
            "global_context": context_text,
            "stages": {k: v.get() for k, v in self.edit_vars.items()}
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    
                self.chunk_size_var.set(config.get("chunk_size", "1500"))
                self.context_size_var.set(config.get("context_size", "8192"))
                self.genre_var.set(config.get("genre", "Sci-Fi"))
                self.voice_var.set(config.get("voice", "None"))
                self.tempo_var.set(config.get("tempo", "None"))
                self.fast_mode_var.set(config.get("fast_mode", False))
                self.autofix_var.set(config.get("auto_fix", True))
                
                saved_context = config.get("global_context", "")
                if saved_context:
                    self.global_context_box.delete("1.0", "end")
                    self.global_context_box.insert("1.0", saved_context)
                
                stages = config.get("stages", {})
                for k, v in stages.items():
                    if k in self.edit_vars:
                        self.edit_vars[k].set(v)
                        
                self.saved_model = config.get("model", "")
            except Exception as e:
                print(f"Failed to load config: {e}")

    def on_closing(self):
        self.save_config()
        self.destroy()

    # --- UI HELPERS ---
    def log(self, message):
        self.after(0, lambda: self.log_area.insert("end", f"{message}\n"))
        self.after(0, lambda: self.log_area.see("end"))

    def set_status(self, text):
        self.status_label.configure(text=text)

    def browse_input(self):
        filename = filedialog.askopenfilename(defaultextension=".docx", filetypes=[("Word Documents", "*.docx")])
        if filename:
            self.input_var.set(filename)
            base, ext = os.path.splitext(filename)
            self.output_var.set(f"{base}_edited{ext}")

    def browse_output(self):
        filename = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word Documents", "*.docx")])
        if filename:
            self.output_var.set(filename)

    def fetch_models(self):
        try:
            req = urllib.request.Request(f"{self.engine.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                models = [m['name'] for m in data.get('models', [])]
                
                if models:
                    self.model_dropdown.configure(values=models)
                    if hasattr(self, 'saved_model') and self.saved_model in models:
                        self.model_var.set(self.saved_model)
                    else:
                        self.model_var.set(models[0])
                    self.log("Models loaded from Ollama.")
                else:
                    self.model_dropdown.configure(values=["No models found"])
        except Exception as e:
            self.log(f"Could not connect to Ollama. Ensure localhost:11434 is running.")
            self.model_dropdown.configure(values=["Connection Error"])

    def stop_process(self):
        if self.is_processing:
            self.engine.cancel_requested = True
            self.stop_btn.configure(state="disabled", text="Stopping...")
            self.log("Cancel requested. Finishing current task...")

    # --- STORY BIBLE EXTRACTION PASS ---
    def start_specs_generation(self):
        if self.is_processing: return
        
        in_file = self.input_var.get()
        model = self.model_var.get()
        
        if not in_file or not os.path.exists(in_file):
            messagebox.showwarning("Missing File", "Please select a valid input docx first.")
            return
        if not model or "Error" in model:
            messagebox.showwarning("No Model", "Please select a valid Ollama model.")
            return

        self.is_processing = True
        self.engine.cancel_requested = False
        self.generate_specs_btn.configure(state="disabled", text="Generating...")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", text="Stop/Cancel")
        self.progress_bar.set(0)
        
        self.global_context_box.delete("1.0", "end")
        self.global_context_box.insert("1.0", "Continuity Director is reading the manuscript. Please wait...\n")
        self.log("Starting Continuity Map-Reduce pass...")
        
        threading.Thread(target=self._run_specs_generation, args=(in_file, model), daemon=True).start()

    def _run_specs_generation(self, in_file, model):
        try:
            max_tokens = int(self.chunk_size_var.get())
            orchestrator = AgentOrchestrator(self.engine)
            
            final_bible = orchestrator.build_continuity_bible(
                input_docx=in_file,
                chunk_size=max_tokens,
                model=model,
                ui_callback=self.set_status,
                progress_callback=self.progress_bar.set
            )
            
            if self.engine.cancel_requested:
                self.after(0, lambda: self.global_context_box.insert("end", "\n[Generation Cancelled]"))
                return
            
            try:
                specs_dir = "/home/ollama/story_bible"
                os.makedirs(specs_dir, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(in_file))[0]
                specs_path = os.path.join(specs_dir, f"{base_name}_bible.txt")
                
                with open(specs_path, "w", encoding="utf-8") as f:
                    f.write(f"Story Bible: {base_name}\n")
                    f.write("=========================================\n\n")
                    f.write(final_bible)
                    
                self.log(f"Story Bible securely saved to: {specs_path}")
            except Exception as file_error:
                self.log(f"Warning: Could not save Story Bible file to disk: {file_error}")
            
            def finalize_ui():
                self.global_context_box.delete("1.0", "end")
                self.global_context_box.insert("1.0", final_bible)
                self.global_context_box.see("end")
                self.progress_bar.set(1.0)
                
            self.after(0, finalize_ui)
            self.log("Story Bible successfully generated.")
            
        except Exception as e:
            self.log(f"\nERROR building continuity: {str(e)}")
            self.after(0, messagebox.showerror, "Error", f"Failed to generate bible:\n{str(e)}")
            
        finally:
            self.is_processing = False
            self.after(0, lambda: self.generate_specs_btn.configure(state="normal", text="🧠 Auto-Extract Story Bible"))
            self.after(0, lambda: self.start_btn.configure(state="normal", text="Start Editing Process"))
            self.after(0, lambda: self.stop_btn.configure(state="disabled", text="Stop/Cancel"))
            self.after(0, self.set_status, "Ready.")
            self.after(0, self.progress_bar.set, 0)

    # --- MAIN AGENT ORCHESTRATION PIPELINE ---
    def start_process(self):
        if self.is_processing: return
        
        in_file = self.input_var.get()
        out_file = self.output_var.get()
        model = self.model_var.get()
        selected_stages = [name for name, var in self.edit_vars.items() if var.get()]
        
        if not in_file or not out_file:
            messagebox.showwarning("Missing Files", "Please select input and output files.")
            return
        if not model or "Error" in model:
            messagebox.showwarning("No Model", "Please select a valid Ollama model.")
            return
        if not selected_stages:
            messagebox.showwarning("No Edits", "Please select at least one editing agent.")
            return

        self.save_config() 
        self.is_processing = True
        self.engine.cancel_requested = False
        
        self.start_btn.configure(state="disabled", text="Agents Working...")
        self.generate_specs_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", text="Stop/Cancel")
        self.progress_bar.set(0)
        self.log_area.delete("1.0", "end")
        
        threading.Thread(target=self._run_pipeline, args=(in_file, out_file, model, selected_stages), daemon=True).start()

    def _run_pipeline(self, in_file, out_file, model, selected_stages):
        try:
            self.log(f"Orchestrating agents for: {os.path.basename(in_file)}")
            max_tokens = int(self.chunk_size_var.get())
            context_limit = int(self.context_size_var.get())
            fast_mode = self.fast_mode_var.get()
            auto_fix = self.autofix_var.get()
            
            style_modifiers = []
            if self.genre_var.get() != "None": style_modifiers.append(f"Format Focus: {self.genre_var.get()}")
            if self.voice_var.get() != "None": style_modifiers.append(f"Tone: {self.voice_var.get()}")
            if self.tempo_var.get() != "None": style_modifiers.append(f"Pacing: {self.tempo_var.get()}")
            
            base_prompt_injection = ""
            if style_modifiers:
                base_prompt_injection += "\n\nSTYLE DIRECTIVES:\n" + "\n".join(f"- {m}" for m in style_modifiers)
            
            raw_context = self.global_context_box.get("1.0", "end-1c").strip()
            if raw_context and not raw_context.startswith("Auto-generate or enter"):
                base_prompt_injection += (
                    f"\n\nGLOBAL MANUSCRIPT CONTEXT/STORY BIBLE:\n"
                    f"{raw_context}"
                )

            # Initialize Agent Roster
            config = {stage: True for stage in selected_stages}
            
            if fast_mode:
                combined_role = "Apply these edits simultaneously:\n" + "\n".join(f"- {s}" for s in selected_stages)
                if auto_fix: combined_role += "\n- Auto-Fix: Actively resolve structural issues and logic gaps smoothly within the text."
                active_agents = [EditorAgent(self.engine, model, "Combined Orchestrator", combined_role, context_limit)]
            else:
                active_agents = create_agents(self.engine, model, config, context_limit)
                
            orchestrator = AgentOrchestrator(self.engine, active_agents, base_prompt_injection)
            
            self.log(f"Routing document through {len(active_agents)} active agents...")
            all_exceptions = orchestrator.edit_document(
                input_docx=in_file, 
                output_docx=out_file, 
                chunk_size=max_tokens,
                ui_callback=self.set_status,
                progress_callback=self.progress_bar.set
            )

            self.log(f"Saved: {os.path.basename(out_file)}")
            
            if all_exceptions:
                exc_file = os.path.splitext(out_file)[0] + "_exceptions.txt"
                with open(exc_file, "w", encoding="utf-8") as f:
                    f.write("Agent System Exceptions Log\n=========================\n\n" + "\n".join(all_exceptions))
                self.log(f"Exceptions saved to {os.path.basename(exc_file)}")
            
            self.after(0, messagebox.showinfo, "Complete", "Agent orchestration finished successfully!")

        except Exception as e:
            self.log(f"\nCRITICAL ERROR: {str(e)}")
            self.after(0, messagebox.showerror, "Error", str(e))
            
        finally:
            self.is_processing = False
            self.after(0, lambda: self.start_btn.configure(state="normal", text="Start Editing Process"))
            self.after(0, lambda: self.generate_specs_btn.configure(state="normal"))
            self.after(0, lambda: self.stop_btn.configure(state="disabled", text="Stop/Cancel"))
            self.after(0, self.set_status, "Ready.")
            self.after(0, self.progress_bar.set, 0)

if __name__ == "__main__":
    app = RoboEditorUI()
    app.mainloop()