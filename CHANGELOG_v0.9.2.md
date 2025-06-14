# Changelog - v0.9.2

## 🚀 New Features

### Auto-Split Long Dialogues
- Dialogues exceeding 3000 characters (excluding tags) are automatically split into multiple chunks
- Each chunk is saved as a separate file (part1, part2, etc.)
- Character counting excludes audio tags so they don't reduce your content capacity
- Preserves all tags for compelling audio generation

### Auto-Adjust Stability Values
- Invalid stability values are automatically rounded to the nearest valid v3 option
- If stability < 0.35 → rounds to 0.0 (Creative)
- If stability ≤ 0.75 → rounds to 0.5 (Natural)
- If stability > 0.75 → rounds to 1.0 (Robust)
- Applied to both `text_to_speech` (v3 model) and `text_to_dialogue`

## 🔧 Improvements

### Better Error Prevention
- Pre-validates character count before API calls
- Provides helpful guidance in tool descriptions
- Reduces failed API calls and token consumption

### Updated Tool Descriptions
- Added character limit warnings to `text_to_dialogue`
- Clarified automatic features in descriptions
- Removed unhelpful "use Studio" suggestions

## 📝 Technical Details

### New Helper Functions
- `count_dialogue_chars()` - Counts actual spoken text, excluding tags
- `split_dialogue_chunks()` - Intelligently splits dialogue at turn boundaries

### Implementation
- Character limit: 2800 chars per chunk (leaves buffer for safety)
- Splits preserve dialogue structure and speaker turns
- Multiple output files are clearly listed in success messages