# Dictation accuracy test script

Use this script to compare models and releases consistently. Speak each item
naturally; do not dictate punctuation names unless the test says to do so.
Record the actual output, obvious errors, and approximate delay after stopping.

## 1. Baseline paragraph

> This morning I reviewed the project plan, answered three messages, and moved
> the meeting to Thursday afternoon. The weather was quiet, the room was calm,
> and I spoke at my normal pace without trying to sound unusually clear.

## 2. Similar-sounding words

> Their team left its notes over there, and they're returning at two, too. I
> accept that the change may affect the result, except when the effect is too
> small to measure. Whether the weather improves depends on the wind.

## 3. Names and technical vocabulary

> Charlie McKenna opened GitHub, reviewed Wordwright, and compared Notion,
> Granola, and Glean. The prototype uses Python, faster-whisper, CTranslate2,
> WASAPI, Markdown, JSON, YAML, PostgreSQL, Kubernetes, NVIDIA, and PyTorch.

## 4. Numbers, dates, and symbols

> On October fifth, twenty twenty-six, version two point zero point one processed
> one thousand two hundred thirty-four records in thirty-seven point five
> seconds. The estimated cost was twelve dollars and forty-nine cents.

For a separate formatting stress test, say:

> My email is charlie dot mckenna at example dot com, and the website is example
> dot com slash projects slash wordwright.

## 5. Corrections and disfluencies

> Please move the blue folder—actually, make that the green folder—to the shared
> drive. I think we should, um, review the first draft before, before we publish
> the final version.

The goal is to observe what the model preserves or removes, not to require a
particular cleanup behavior yet.

## 6. Fast speech

Read the baseline paragraph again at a comfortably fast conversational pace,
without exaggerating your pronunciation.

## 7. Difficult articulation

> The rural juror rarely worries. Six sleek swans swam swiftly south. Unique New
> York, red leather, yellow leather, and truly rural brewery.

## 8. Pauses

Say the following with a five-second pause at each ellipsis:

> The first point is accuracy ... the second point is privacy ... and the third
> point is whether the text appears where I expect it.

Repeat it with short one-second pauses.

## 9. Environmental tests

Repeat the baseline paragraph under each condition:

- Normal room conditions
- Keyboard typing in the background
- A fan or music playing quietly
- Speaking softly
- Speaking from farther away from the microphone
- Turning your head briefly away from the microphone

## 10. Longer natural dictation

Speak freely for two minutes about a familiar topic. Include a few natural
pauses and self-corrections. This is the most representative test of real use.

## Results template

| Test | Model | Delay | Errors or observations |
| --- | --- | ---: | --- |
| Baseline | `small.en` | | |
| Similar sounds | `small.en` | | |
| Technical vocabulary | `small.en` | | |
| Numbers | `small.en` | | |
| Corrections | `small.en` | | |
| Fast speech | `small.en` | | |
| Articulation | `small.en` | | |
| Long pauses | `small.en` | | |
| Background noise | `small.en` | | |
| Two-minute dictation | `small.en` | | |

