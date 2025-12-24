"""
model_manager.py - SpaCy Model Manager

Handles dynamic loading, installation, and fallback logic for SpaCy models.
Uses langdetect for automatic source language detection.
"""

import os
import sys
import json
import re
import subprocess
from typing import Optional, Tuple, List, Dict, Any
import spacy
from spacy.util import is_package

try:
    from langdetect import detect, DetectorFactory
    # Make langdetect deterministic
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

from backend.language_data import (
    PRESET_MODELS, 
    ALL_LANGUAGES, 
    SPACY_BLANK_LANGUAGES,
    get_language_name
)


class ModelManager:
    """
    Manages SpaCy models with dynamic loading, auto-detection, and fallback.
    
    Features:
    - On-demand model installation via subprocess
    - Auto language detection using langdetect
    - Smart fallback to rule-based sentencizer
    - Hot-reload without server restart
    """
    
    CONFIG_FILE = "models.json"
    
    def __init__(self):
        self._loaded_models: Dict[str, spacy.Language] = {}
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load models configuration from JSON file."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._config = {"models": []}
        else:
            self._config = {"models": []}
    
    def _save_config(self) -> None:
        """Save models configuration to JSON file."""
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def is_setup_complete(self) -> bool:
        """Check if initial setup has been completed."""
        return os.path.exists(self.CONFIG_FILE) and len(self._config.get("models", [])) > 0
    
    def get_installed_models(self) -> List[Dict[str, str]]:
        """Get list of installed and configured models."""
        return self._config.get("models", [])
    
    def get_active_model_info(self) -> Optional[Dict[str, str]]:
        """Get info about the primary (first) installed model."""
        models = self.get_installed_models()
        return models[0] if models else None
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        Detect the language of the given text.
        
        Returns:
            Tuple of (iso_code, confidence) or ("unknown", 0.0) if detection fails
        """
        if not LANGDETECT_AVAILABLE:
            return ("unknown", 0.0)
        
        # Need enough text for reliable detection
        if len(text.strip()) < 20:
            return ("unknown", 0.0)
        
        try:
            detected = detect(text)
            # langdetect doesn't provide confidence directly, estimate based on text length
            confidence = min(0.95, 0.5 + len(text) / 1000)
            return (detected, confidence)
        except Exception:
            return ("unknown", 0.0)
    
    def get_model_for_language(self, lang_code: str) -> Tuple[spacy.Language, str, bool]:
        """
        Get appropriate SpaCy model for the given language code.
        
        Args:
            lang_code: ISO 639-1 language code (e.g., 'en', 'tr')
            
        Returns:
            Tuple of (nlp_model, model_name, is_fallback)
            is_fallback is True if using sentencizer instead of proper model
        """
        # Check if we have a model for this language
        installed = self.get_installed_models()
        
        # Direct match
        for model in installed:
            if model.get("lang_code") == lang_code:
                model_name = model.get("model_name")
                nlp = self._load_model(model_name)
                if nlp:
                    return (nlp, model_name, False)
        
        # Check for multilingual model (xx)
        for model in installed:
            if model.get("lang_code") == "xx" or "xx_" in model.get("model_name", ""):
                model_name = model.get("model_name")
                nlp = self._load_model(model_name)
                if nlp:
                    return (nlp, model_name, False)
        
        # Fallback: Use first available model (with warning flag)
        if installed:
            first_model = installed[0]
            model_name = first_model.get("model_name")
            nlp = self._load_model(model_name)
            if nlp:
                return (nlp, model_name, True)  # True = mismatch warning
        
        # Last resort: Rule-based sentencizer
        nlp = self._create_sentencizer(lang_code)
        return (nlp, f"sentencizer ({lang_code})", True)
    
    def _load_model(self, model_name: str) -> Optional[spacy.Language]:
        """Load a SpaCy model with caching."""
        if model_name in self._loaded_models:
            return self._loaded_models[model_name]
        
        try:
            if is_package(model_name):
                nlp = spacy.load(model_name)
                self._loaded_models[model_name] = nlp
                print(f"  ✓ Loaded model: {model_name}")
                return nlp
        except Exception as e:
            print(f"  ✗ Failed to load {model_name}: {e}")
        
        return None
    
    def _create_sentencizer(self, lang_code: str) -> spacy.Language:
        """Create a rule-based sentencizer for the given language."""
        spacy_lang = SPACY_BLANK_LANGUAGES.get(lang_code, "xx")
        
        try:
            nlp = spacy.blank(spacy_lang)
        except Exception:
            nlp = spacy.blank("xx")
        
        nlp.add_pipe("sentencizer")
        print(f"  ✓ Created sentencizer for: {lang_code}")
        return nlp
    
    # Turkish model URL - uses loose versioning compatible with SpaCy 3.8+
    TURKISH_MODEL_URL = "https://huggingface.co/turkish-nlp-suite/tr_core_news_lg/resolve/main/tr_core_news_lg-1.0-py3-none-any.whl"
    
    def install_model(self, install_cmd: str, model_name: str, lang_code: str) -> Dict[str, Any]:
        """
        Install a SpaCy model via subprocess.
        
        CRITICAL: Uses sys.executable to ensure installation happens in the active venv.
        
        Args:
            install_cmd: Full install command (e.g., 'python -m spacy download en_core_web_sm')
            model_name: Model name for loading (e.g., 'en_core_web_sm')
            lang_code: ISO language code (e.g., 'en')
            
        Returns:
            Dict with 'success', 'message', and optional 'error' keys
        """
        # Validate command (unless we're overriding for Turkish)
        if lang_code.lower() != "tr":
            validation = self._validate_install_command(install_cmd)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}
        
        try:
            # SPECIAL CASE: Turkish model requires Hugging Face wheel for SpaCy 3.8 compatibility
            if lang_code.lower() == "tr":
                print(f"  🇹🇷 Installing Turkish model from Hugging Face (SpaCy 3.8 compatible)...")
                cmd_list = [
                    sys.executable, "-m", "pip", "install", 
                    self.TURKISH_MODEL_URL
                ]
                model_name = "tr_core_news_lg"  # Override to ensure correct name
            else:
                # Parse the command and build a secure command list
                cmd_list = self._build_safe_command(install_cmd)
            
            print(f"  📦 Running: {' '.join(cmd_list[:4])}...")
            
            # Run installation using sys.executable to respect venv
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Verify installation
                if is_package(model_name):
                    # Add to config
                    new_model = {
                        "lang_code": lang_code,
                        "model_name": model_name,
                        "language_name": get_language_name(lang_code)
                    }
                    
                    # Avoid duplicates
                    models = self._config.get("models", [])
                    if not any(m.get("model_name") == model_name for m in models):
                        models.append(new_model)
                        self._config["models"] = models
                        self._save_config()
                    
                    return {
                        "success": True,
                        "message": f"Successfully installed {model_name}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Installation completed but model '{model_name}' not found. Check output: {result.stdout[-500:]}"
                    }
            else:
                # Show both stderr and stdout for better debugging
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                # Check for common error patterns
                if "No compatible package found" in error_msg:
                    return {
                        "success": False,
                        "error": f"Model '{model_name}' is not compatible with your SpaCy version. Try a different model or update SpaCy."
                    }
                return {
                    "success": False,
                    "error": f"Installation failed: {error_msg[-500:]}"
                }
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timed out (5 minutes)"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_safe_command(self, install_cmd: str) -> List[str]:
        """
        Build a safe command list from the install command string.
        Always uses sys.executable to respect the active virtual environment.
        """
        cmd_lower = install_cmd.lower().strip()
        
        # Case 1: pip install <url or package>
        # e.g., "pip install https://..." or "pip install spacy-model"
        if cmd_lower.startswith("pip install"):
            args = install_cmd.split()[2:]  # Everything after "pip install"
            return [sys.executable, "-m", "pip", "install"] + args
        
        # Case 2: python -m pip install <package>
        if "pip" in cmd_lower and "install" in cmd_lower:
            # Find 'install' position and get everything after
            parts = install_cmd.split()
            try:
                install_idx = [p.lower() for p in parts].index("install")
                args = parts[install_idx + 1:]
                return [sys.executable, "-m", "pip", "install"] + args
            except ValueError:
                pass
        
        # Case 3: python -m spacy download <model>
        if "spacy" in cmd_lower and "download" in cmd_lower:
            parts = install_cmd.split()
            try:
                download_idx = [p.lower() for p in parts].index("download")
                model_args = parts[download_idx + 1:]
                return [sys.executable, "-m", "spacy", "download"] + model_args
            except ValueError:
                pass
        
        # Fallback: Replace 'python' or 'pip' with sys.executable
        parts = install_cmd.split()
        if parts[0].lower() in ("python", "python3"):
            parts[0] = sys.executable
        elif parts[0].lower() == "pip":
            parts = [sys.executable, "-m", "pip"] + parts[1:]
        
        return parts
    
    def _validate_install_command(self, cmd: str) -> Dict[str, Any]:
        """Validate install command for security - allows flexible pip/spacy commands and URLs."""
        cmd_lower = cmd.lower().strip()
        
        # Must contain 'spacy' or 'pip' or be a URL
        has_spacy = "spacy" in cmd_lower
        has_pip = "pip" in cmd_lower
        is_url = cmd_lower.startswith("http://") or cmd_lower.startswith("https://")
        
        if not (has_spacy or has_pip or is_url):
            return {"valid": False, "error": "Command must contain 'spacy', 'pip', or be a URL"}
        
        # Block dangerous shell operators
        dangerous_patterns = ["&&", "||", ";", "|", "$", "`", "$(", "${", ">", "<", "\n", "\r"]
        for pattern in dangerous_patterns:
            if pattern in cmd:
                return {"valid": False, "error": f"Invalid shell operator '{pattern}' in command"}
        
        return {"valid": True}
    
    def remove_model(self, model_name: str, uninstall: bool = True) -> Dict[str, Any]:
        """
        Remove a model from configuration and optionally uninstall from pip.
        
        Args:
            model_name: Name of the model to remove
            uninstall: If True, also pip uninstall the package
            
        Returns:
            Dict with 'success' and 'message' keys
        """
        models = self._config.get("models", [])
        new_models = [m for m in models if m.get("model_name") != model_name]
        
        if len(new_models) == len(models):
            return {"success": False, "error": f"Model '{model_name}' not found in configuration"}
        
        # Update config first
        self._config["models"] = new_models
        self._save_config()
        
        # Clear from cache
        if model_name in self._loaded_models:
            del self._loaded_models[model_name]
        
        # Actually uninstall the package
        if uninstall:
            try:
                print(f"  🗑️ Uninstalling {model_name}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", "-y", model_name],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    print(f"  ✓ Uninstalled {model_name}")
                    return {"success": True, "message": f"Model '{model_name}' removed and uninstalled"}
                else:
                    # Package might already be gone, still success for config removal
                    print(f"  ⚠️ pip uninstall returned non-zero, but config was updated")
                    return {"success": True, "message": f"Model '{model_name}' removed from config (pip: {result.stderr.strip()[:100]})"}
                    
            except subprocess.TimeoutExpired:
                return {"success": True, "message": f"Model '{model_name}' removed from config (uninstall timed out)"}
            except Exception as e:
                return {"success": True, "message": f"Model '{model_name}' removed from config (uninstall error: {str(e)[:100]})"}
        
        return {"success": True, "message": f"Model '{model_name}' removed from configuration"}
    
    def reload(self) -> None:
        """Reload configuration and clear model cache."""
        self._loaded_models.clear()
        self._load_config()
        print("  🔄 ModelManager reloaded")


# Singleton instance
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the singleton ModelManager instance."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
