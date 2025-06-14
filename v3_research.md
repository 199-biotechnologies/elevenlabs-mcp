# ElevenLabs v3 Audio Tags and Best Practices Research

## Overview
ElevenLabs v3 (alpha) is their most expressive Text to Speech model, offering emotional depth, rich delivery, and support for 70+ languages. It introduces inline audio tags for controlling emotion, delivery, and direction.

## Key Features
- **Multiple speakers (Dialogue Mode)**: Create dynamic conversations between speakers
- **Audio Tag Support**: Full range of emotions, direction and audio effects
- **Languages**: 70+ languages supported
- **80% discount**: Until end of June 2025 for self-serve users through UI

## Audio Tags

### Voice-Related Tags
Control vocal delivery and emotional expression:
- `[laughs]`, `[laughs harder]`, `[starts laughing]`, `[wheezing]`
- `[whispers]`, `[whispering]`
- `[sighs]`, `[exhales]`
- `[sarcastic]`, `[curious]`, `[excited]`, `[crying]`, `[snorts]`, `[mischievously]`
- `[frustrated sigh]`, `[happy gasp]`
- `[excitedly]`, `[curiously]`, `[impressed]`, `[dramatically]`
- `[giggling]`, `[delighted]`, `[amazed]`, `[warmly]`
- `[softly]`
- `[SHOUTING]` (using capitalization)

### Sound Effects Tags
Add environmental sounds and effects:
- `[gunshot]`, `[applause]`, `[clapping]`, `[explosion]`
- `[swallows]`, `[gulps]`

### Unique and Special Tags (Experimental)
- `[strong X accent]` (replace X with desired accent, e.g., `[strong French accent]`)
- `[sings]`, `[woo]`, `[fart]`

## Best Practices

### 1. Voice Selection
- **Most important parameter** - voice must be similar to desired delivery
- Choose voices strategically:
  - **Emotionally diverse**: Include varied emotional tones for expressive IVCs
  - **Targeted niche**: Maintain consistent emotion for specific use cases
  - **Neutral**: More stable across languages and styles
- Professional Voice Clones (PVCs) not fully optimized for v3 yet

### 2. Settings - Stability Slider
Controls adherence to original reference audio:
- **Creative**: More emotional/expressive but prone to hallucinations
- **Natural**: Balanced and neutral, closest to original
- **Robust**: Highly stable but less responsive to directional prompts

### 3. Prompt Length
- Avoid very short prompts (< 250 characters) for consistent outputs
- Longer prompts generally produce better results

### 4. Punctuation and Formatting
- **Ellipses (…)**: Add pauses and weight
- **Capitalization**: Increases emphasis (e.g., "VERY")
- **Standard punctuation**: Provides natural speech rhythm

### 5. Tag Usage Guidelines
- Match tags to voice character (don't use `[shout]` on whispering voice)
- Tags are voice and context dependent
- Can combine multiple tags for complex delivery
- Use natural speech patterns and clear emotional context

### 6. Multi-Speaker Dialogue
- Assign distinct voices from Voice Library for each speaker
- Speakers share context and emotion for natural conversations
- Can create interruptions and overlapping speech

## Example Usage

### Single Speaker
```
[whispers] I never knew it could be this way, but I'm glad we're here.
```

```
It was a VERY long day [sigh] … nobody listens anymore.
```

```
[strong French accent] "Zat's life, my friend — you can't control everysing."
```

### Multi-Speaker Dialogue
```
Speaker 1: [excitedly] Sam! Have you tried the new Eleven V3?
Speaker 2: [curiously] Just got it! The clarity is amazing. I can actually do whispers now—[whispers] like this!
```

## Limitations and Notes
- API access coming soon (currently UI only)
- Some experimental tags may be inconsistent across voices
- Voice training samples affect tag effectiveness
- PVCs (Professional Voice Clones) not fully optimized yet

## Supported Languages (70+)
Afrikaans, Arabic, Armenian, Assamese, Azerbaijani, Belarusian, Bengali, Bosnian, Bulgarian, Catalan, Cebuano, Chichewa, Croatian, Czech, Danish, Dutch, English, Estonian, Filipino, Finnish, French, Galician, Georgian, German, Greek, Gujarati, Hausa, Hebrew, Hindi, Hungarian, Icelandic, Indonesian, Irish, Italian, Japanese, Javanese, Kannada, Kazakh, Kirghiz, Korean, Latvian, Lingala, Lithuanian, Luxembourgish, Macedonian, Malay, Malayalam, Mandarin Chinese, Marathi, Nepali, Norwegian, Pashto, Persian, Polish, Portuguese, Punjabi, Romanian, Russian, Serbian, Sindhi, Slovak, Slovenian, Somali, Spanish, Swahili, Swedish, Tamil, Telugu, Thai, Turkish, Ukrainian, Urdu, Vietnamese, Welsh

## Tips for Experimentation
- Try different tag combinations
- Match tags to voice character
- Use proper text structure
- Experiment with descriptive emotional states beyond documented tags
- Test thoroughly before production use