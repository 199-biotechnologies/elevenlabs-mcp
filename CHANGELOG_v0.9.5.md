# Changelog - v0.9.5

## 🚀 New Features

### Smart Tag Simplification
- Automatically converts complex/compound tags to valid v3 tags
- Examples:
  - `[final, broken whisper]` → `[whispers]`
  - `[philosophical rage]` → `[thoughtful]`
  - `[building to climax]` → `[excited]`
  - `[barely audible]` → `[whispers]`
- Removes invalid stage directions like `[to the heavens]`
- Preserves working tags like `[hysterical]`, `[crazy laugh]`, `[nervous laugh]`

### Dynamic Timeout Calculation
- Prevents timeouts on complex dialogues
- Calculates timeout based on:
  - Number of inputs (15 seconds per input)
  - Tag count (3 seconds per tag)
  - Total text length
- Max timeout: 5 minutes with warning for complex content

### Tag Validation
- Warns about invalid tags before processing
- Suggests valid alternatives
- Based on comprehensive list of v3-supported tags

## 🔧 Improvements

### Enhanced Tag Support
- Added more emotional tags: hysterical, crazy laugh, nervous laugh
- Added voice variations: trembling voice, voice breaking, voice cracking
- Added action tags: frustrated sigh, happy gasp

### Better Error Prevention
- Pre-processes tags to avoid quality issues
- Validates tags against known working list
- Provides helpful warnings without failing

## 📝 Technical Details

### New Functions
- `simplify_tags()` - Converts complex tags to simple v3 tags
- `validate_and_warn_tags()` - Checks and warns about invalid tags
- `calculate_dialogue_timeout()` - Dynamic timeout calculation

### Valid v3 Tags List
Comprehensive set including emotions, voice styles, actions, and sound effects