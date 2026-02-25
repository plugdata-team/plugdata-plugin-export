# Automated build script for plugdata powered plugins

Note: this is currently still in development, don't use this in production yet!

1. Fork this repository.
2. Click on the "Actions" tab and enable github actions
3. Add your patch files and plugin definitions to config.json.
4. Wait for GitHub Actions to complete the build.
5. Download your VST3 / AU / CLAP / LV2 / Standalone plugins!


# Config syntax

Example:
```
[
  {
    "name": "N-SPEC COMP LITE 2",
    "author": "Nasko",
    "path": "Plugins/N-SPEC COMP LITE 2.zip",
    "patch": "N-SPEC COMP LITE 2.pd",
    "formats": ["VST3", "AU", "LV2", "CLAP"],
    "type": "fx",
    "version": "1.0.0",
    "enable_gem": false,
    "enable_sfizz": false,
    "enable_ffmpeg": false
  },
  {
    "name": "N-TILT",
    "author": "Nasko",
    "path": "Plugins/N-TILT.zip",
    "patch": "N-TILT.pd",
    "formats": ["Standalone"],
    "type": "fx",
    "version": "1.0.0",
    "enable_gem": false,
    "enable_sfizz": false,
    "enable_ffmpeg": false
  }
]
```

## Parameter Reference

### Required Fields

| Field     | Type     | Description |
|-----------|----------|-------------|
| `name`    | `string` | **Unique name** of the plugin. This is how it will appear in your DAW. <br>_Note: You cannot load two plugdata plugins with the same name._ |
| `author`  | `string` | Name of the plugin's creator, displayed inside the DAW. |
| `path`    | `string` | Path to the patch location within the repository. Can be a **folder** or a **.zip** file. |
| `patch`   | `string` | File name of the patch within the zip file or folder, must be a **.pd** file |
| `formats` | `array`  | List of plugin formats to build. Valid values: `VST3`, `AU`, `CLAP`, `LV2`, `Standalone`. |
| `type`    | `string` | Type of plugin: either `"fx"` for effects or `"instrument"` for instruments/synths. |
---

### Optional Fields

| Field           | Type      | Description |
|------------------|-----------|-------------|
| `version`        | `string`  | Plugin version, new versions will not install correctly unless you increment this. <br>_Default: `1.0.0`_ |
| `enable_gem`     | `boolean` | Enables experimental [GEM](https://puredata.info/downloads/Gem) support <br>_Default: `false`_ |
| `enable_sfizz`   | `boolean` | Enables the `[sfz~]` object for SFZ sample playback. <br>_Default: `false`_ |
| `enable_ffmpeg`  | `boolean` | Enables FFmpeg-based audio objects. <br>Recommended if your patch plays audio files. <br>_Default: `false`_ |

# Running locally

You can also run the build script locally instead of through github actions:
```
python3 build.py
```
You can use the `--generator` flag to set the project cmake generates. Valid values are `xcode`, `visualstudio` or `ninja` (default).
Aditionally, you can use the `--configure-only` flag if you want to skip the build step.

# Licensing note
After building, the original patch file you used is directly accessible via the “Info” menu in the plugin. This is required to comply with the GPL license (required by both plugdata and the JUCE GPL tier), as your patch could now legally be considered as "source code" of the generated plugins.
