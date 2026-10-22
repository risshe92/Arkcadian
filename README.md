

# Summary

## TLDR

Modern DJ software primarily relies on BPM and key, while energy is often assessed by ear. 
Although useful, these metrics do not fully describe a track's musical characteristics.

Two tracks can share the same BPM, key, and energy yet differ significantly in sound, rhythm, atmosphere, and emotional character. Furthermore, musical emotion is subjective and may be interpreted differently by each listener.

This program aims to bridge that information gap by analysing additional measurable characteristics, including loudness, brightness, rhythmic activity, vocals, basslines, and energy.

The results are embedded directly into each track's metadata, with raw measurements and simplified 1–5 ratings where applicable.

# # Problem statement

Modern DJ software and equipment provide several tools to help DJs organise tracks and plan their sets.
However, the most commonly used musical metrics are:

- BPM

- Key

- Energy
  *(although this is often determined through listening and personal judgement)*

  These metrics are useful; thought they provide only a limited picture of a track's overall musical characteristics.

  however it might limit one's creative process; as other metrics would require manual intervention and rely on the individual's interpretation of the track. 

  i.e. 

  - Different Track, same metrics; but different emotions;
    Two track might share the same BPM, Key and energy, but they might differ in the "mood" it attempts to invoke 

  - Same track, different interpretation of the mood 

    the same track might invoke one emotion to one person and another emotion to another person

|            | Jane          | Tom                  |
| ---------- | ------------- | -------------------- |
| BPM        | 138           | 138                  |
| Key        | 8A            | 8A                   |
| Energy     | High          | Medium               |
| Emotion    | Sad, euphoric | Uplifting, nostalgic |
| Atmosphere | Melancholic   | Dreamy               |

**This is because: The audio is identical, but the interpretation differs.**

Traditional BPM and key information alone cannot describe these differences.

## The Emotional Nature of Music

Music communicates a wide range of emotions;
Emotions can be communicated through combinations of:

- Melody and harmony
- Chord progressions
- Rhythm and basslines
- Timbre and instrumentation
- Dynamics, tension, and release

### Comparison between Carnatic music And Western music

#### Carnatic 

Carnatic music uses a system of ragas, each with its own melodic identity, characteristic phrases, and traditional emotional associations.

- Gamakas (ornamentations) and characteristic phrases contribute strongly to its emotional expression.
- A single melodic line can communicate powerful emotions without chords.

#### Western music:

- Emotions are often communicated through chord progressions, major/minor tonality, dynamics, rhythm, and instrumentation.
- A single scale doesn't typically carry the same established expressive identity as a raga.
- Western music can absolutely express sensuality, sorrow, joy, longing, and other complex emotions.

When one uses carnatic music; they are binded by strict rules and regulation; in western music; you are are not binded by rules, you are "advised" to follow the rules. 

### Common approach when planning a set:

This resembles a bell-shaped curve, where intensity increases towards a peak before gradually decreasing.
While this approach can work well, it does not necessarily account for all the musical characteristics that contribute to a set.
For example, two trance tracks might share:

- 138 BPM
- Compatible Camelot keys
- Similar energy ratings

Yet one might have an aggressive rolling bassline and dense percussion, while the other has a softer bassline, spacious arrangement, and prominent vocals.

Despite having similar energy, these tracks may serve very different purposes within a DJ set. Energy alone cannot describe the full character of a track.

A DJ set also involves contrast, musical progression, tension, release, and the relationship between consecutive tracks. These qualities are largely assessed by the DJ through listening and experience.

# What does this program tries to address:

The Program  aims to provide DJs with additional measurable information about their music

The program analyses the following metrics for each track and embeds them to the metadata:

1. Silence
2. Tempo and beat grid
3. Key
4. Loudness
5. Sound character
6. Vocals and structure
7. Low end and bassline
8. Energy



> [!NOTE]
>
> *Refer to Metrics Definitions for more information*

Most measurements are stored twice:

- raw value
   full precision (tag name ends in `_RAW`) 

- display rating from 1 to 5

---

# How Does it Work:

## Pipeline:



## Metrics

![image-20261022164739723](/home/ragnar/.config/Typora/typora-user-images/image-20261022164739723.png)

### Ratings: 

![image-20261022164817818](/home/ragnar/.config/Typora/typora-user-images/image-20261022164817818.png)



### Tagging

The tagging formats used follows the industry standard used in professional DJ equipment and software 

> [!NOTE]
>
> Refer to tagging references



1. Silence (step `silence`)

| Tag             | Type   | Unit / format       | Notes                                     |
| --------------- | ------ | ------------------- | ----------------------------------------- |
| `SILENCE_FOUND` | Yes/no | `1` / `0`           | Silence at the start or end               |
| `MUSIC_START`   | Time   | seconds, 3 decimals | `0.000` after trimming                    |
| `MUSIC_END`     | Time   | seconds, 3 decimals |                                           |
| `TRIMMED`       | Yes/no | `1` / `0`           | `1` when `--trim-silence` removed silence |

2. Tempo (step `tempo`)

| Tag         | Type         | Unit / format  | Notes                                             |
| ----------- | ------------ | -------------- | ------------------------------------------------- |
| `BPM`       | Standard tag | whole number   | Required by the ID3 spec (TBPM). Read by DJ apps. |
| `BPM_EXACT` | Value        | BPM, 1 decimal | Rounded on purpose for DJ use                     |

3. Beat grid (step `beatgrid`)

| Tag              | Type | Unit / format                          | Notes                                                        |
| ---------------- | ---- | -------------------------------------- | ------------------------------------------------------------ |
| `FIRST_DOWNBEAT` | Time | seconds, 3 decimals                    | Beat 1 of the first bar                                      |
| `TEMPO_CHANGES`  | List | `time:bpm,time:bpm` (3 and 1 decimals) | **Only written when the tempo changes.** Example: `0.000:124.5,120.300:128.2` |

4. Key (step `key`)

| Tag          | Type         | Unit / format                                          | Notes                                                        |
| ------------ | ------------ | ------------------------------------------------------ | ------------------------------------------------------------ |
| `INITIALKEY` | Standard tag | Musical notation, max 3 characters (`Am`, `F#m`, `Bb`) | ID3 TKEY. Not written when S-KEY's confidence is below 0.30. |

5. Loudness (step `loudness`)

| Tag                       | Type         | Unit / format           | Notes                                        |
| ------------------------- | ------------ | ----------------------- | -------------------------------------------- |
| `REPLAYGAIN_TRACK_GAIN`   | Standard tag | `-6.52 dB` (2 decimals) | ReplayGain 2.0, from rsgain                  |
| `REPLAYGAIN_TRACK_PEAK`   | Standard tag | `0.988553` (6 decimals) | Linear sample peak, not dB                   |
| `INTEGRATED_LOUDNESS_RAW` | Raw          | LUFS                    | FFmpeg EBU R128, measured on the final file  |
| `INTEGRATED_LOUDNESS`     | Display      | 1–5                     | See ratings                                  |
| `LOUDNESS_RANGE_RAW`      | Raw          | LU                      | Not written for audio shorter than 10 s      |
| `LOUDNESS_RANGE`          | Display      | 1–5                     | Higher = more variation, **not** more energy |

6. Features (step `features`)

| Tag                 | Type    | Unit / format     | Notes             |
| ------------------- | ------- | ----------------- | ----------------- |
| `BRIGHTNESS_RAW`    | Raw     | Hz                | Spectral centroid |
| `BRIGHTNESS`        | Display | 1–5               |                   |
| `ONSET_DENSITY_RAW` | Raw     | onsets per second | Not capped        |
| `ONSET_DENSITY`     | Display | 1–5               |                   |

7. Vocals (step `vocals`)

| Tag                 | Type    | Unit / format | Notes                                    |
| ------------------- | ------- | ------------- | ---------------------------------------- |
| `VOCAL_DENSITY_RAW` | Raw     | 0–1           | Share of the music with singing (Demucs) |
| `VOCAL_DENSITY`     | Display | 1–5           |                                          |

8. Low end (step `lowend`)

| Tag                         | Type             | Unit / format      | Notes                                     |
| --------------------------- | ---------------- | ------------------ | ----------------------------------------- |
| `LOW_END_ONSET_DENSITY_RAW` | Raw (diagnostic) | attacks per second | 30–150 Hz band of the full mix            |
| `LOW_END_OCCUPANCY_RAW`     | Raw (diagnostic) | 0–1                | Share of the music with any low-end sound |
| `LOW_END_ENERGY_RATIO_RAW`  | Raw (diagnostic) | 0–1                | Low-band energy ÷ total energy            |
| `LOW_END_ACTIVITY_RAW`      | Raw (composite)  | 0–1                | `min(1, LOW_END_ONSET_DENSITY_RAW / 4.0)` |
| `LOW_END_ACTIVITY`          | Display          | 1–5                |                                           |

9. Bassline (step `bassline`)

| Tag                          | Type             | Unit / format      | Notes                                                        |
| ---------------------------- | ---------------- | ------------------ | ------------------------------------------------------------ |
| `BASSLINE_ONSET_DENSITY_RAW` | Raw (diagnostic) | attacks per second | Demucs bass stem, full range                                 |
| `BASSLINE_OCCUPANCY_RAW`     | Raw (diagnostic) | 0–1                | Share of the music with an active bass stem                  |
| `BASSLINE_ACTIVITY_RAW`      | Raw (composite)  | 0–1                | `min(1, BASSLINE_ONSET_DENSITY_RAW / 3.0) × min(1, BASSLINE_OCCUPANCY_RAW / 0.4)` |
| `BASSLINE_ACTIVITY`          | Display          | 1–5                |                                                              |

10. Structure (step `structure`)

| Tag            | Type | Unit / format       | Notes                                                    |
| -------------- | ---- | ------------------- | -------------------------------------------------------- |
| `INTRO_LENGTH` | Time | seconds, 3 decimals | Music start → first vocals. No vocals: → first downbeat. |
| `OUTRO_LENGTH` | Time | seconds, 3 decimals | Last vocals → music end. No vocals: last downbeat → end. |

11. Energy (step `energy`)

| Tag          | Type            | Unit / format | Notes                                       |
| ------------ | --------------- | ------------- | ------------------------------------------- |
| `ENERGY_RAW` | Raw (composite) | 0–1           | `0.4×L + 0.2×B + 0.2×O + 0.2×T` (see below) |
| `ENERGY`     | Display         | 1–5           |                                             |

`ENERGY_RAW` inputs, each scaled to 0–1 and clipped:# Problem statement
Modern DJ software and equipment provide several tools to help DJs organise tracks and plan their sets.
However, the most commonly used musical metrics are:

BPM

Key

Energy
(although this is often determined through listening and personal judgement)

These metrics are useful; thought they provide only a limited picture of a track's overall musical characteristics.

however it might limit one's creative process; as other metrics would require manual intervention and rely on the individual's interpretation of the track. 

i.e. 

Different Track, same metrics; but different emotions;
Two track might share the same BPM, Key and energy, but they might differ in the "mood" it attempts to invoke 

Same track, different interpretation of the mood 

the same track might invoke one emotion to one person and another emotion to another person

| Input            | From                                 | Low (= 0) | High (= 1) | Weight |
| ---------------- | ------------------------------------ | --------- | ---------- | ------ |
| L: loudness      | −18 − `REPLAYGAIN_TRACK_GAIN` (LUFS) | −30       | −6         | 0.4    |
| B: brightness    | `BRIGHTNESS_RAW` (Hz)                | 500       | 4,000      | 0.2    |
| O: onset density | `ONSET_DENSITY_RAW` (/s)             | 0         | 6          | 0.2    |
| T: tempo         | exact BPM                            | 60        | 180        | 0.2    |

---

Rating boundaries (display tags)

The rating is 1 plus the number of boundaries the raw value has reached (value ≥ boundary).

| Display tag           | Raw unit | 1         | 2             | 3               | 4               | 5       | Added in |
| --------------------- | -------- | --------- | ------------- | --------------- | --------------- | ------- | -------- |
| `ENERGY`              | 0–1      | < 0.20    | 0.20 – < 0.40 | 0.40 – < 0.60   | 0.60 – < 0.80   | ≥ 0.80  | v1.1     |
| `VOCAL_DENSITY`       | 0–1      | < 0.20    | 0.20 – < 0.40 | 0.40 – < 0.60   | 0.60 – < 0.80   | ≥ 0.80  | v1.1     |
| `BRIGHTNESS`          | Hz       | exactly 0 | > 0 – < 1,500 | 1,500 – < 2,200 | 2,200 – < 2,800 | ≥ 2,800 | v1.1     |
| `ONSET_DENSITY`       | /s       | exactly 0 | > 0 – < 2.00  | 2.00 – < 3.00   | 3.00 – < 4.50   | ≥ 4.50  | v1.1     |
| `INTEGRATED_LOUDNESS` | LUFS     | < −14     | −14 – < −11   | −11 – < −9      | −9 – < −7       | ≥ −7    | v1.2     |
| `LOUDNESS_RANGE`      | LU       | < 4       | 4 – < 6       | 6 – < 8         | 8 – < 11        | ≥ 11    | v1.2     |
| `LOW_END_ACTIVITY`    | 0–1      | < 0.20    | 0.20 – < 0.40 | 0.40 – < 0.60   | 0.60 – < 0.80   | ≥ 0.80  | v1.2     |
| `BASSLINE_ACTIVITY`   | 0–1      | < 0.20    | 0.20 – < 0.40 | 0.40 – < 0.60   | 0.60 – < 0.80   | ≥ 0.80  | v1.2     |

Meaning of the ratings:

| Tag                   | 1                              | 5                            |
| --------------------- | ------------------------------ | ---------------------------- |
| `ENERGY`              | Very low                       | Very high                    |
| `VOCAL_DENSITY`       | Mostly instrumental            | Near-continuous vocals       |
| `BRIGHTNESS`          | No measurable brightness       | Very bright                  |
| `ONSET_DENSITY`       | No onsets                      | Busy                         |
| `INTEGRATED_LOUDNESS` | Quieter than streaming level   | Extremely loud               |
| `LOUDNESS_RANGE`      | Flat, constant intensity       | Big breakdowns, very dynamic |
| `LOW_END_ACTIVITY`    | Little low-end rhythm          | Very busy low end            |
| `BASSLINE_ACTIVITY`   | Little or no bassline movement | Very active bassline         |

---

Summary by type

| Type                               | Tags                                                         |
| ---------------------------------- | ------------------------------------------------------------ |
| Standard tags (read by other apps) | `BPM`, `INITIALKEY`, `REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK` |
| Raw values with a display rating   | `ENERGY`, `VOCAL_DENSITY`, `BRIGHTNESS`, `ONSET_DENSITY`, `INTEGRATED_LOUDNESS`, `LOUDNESS_RANGE`, `LOW_END_ACTIVITY`, `BASSLINE_ACTIVITY` (8 pairs, 16 tags) |
| Raw diagnostics only               | `LOW_END_ONSET_DENSITY_RAW`, `LOW_END_OCCUPANCY_RAW`, `LOW_END_ENERGY_RATIO_RAW`, `BASSLINE_ONSET_DENSITY_RAW`, `BASSLINE_OCCUPANCY_RAW` |
| Times                              | `MUSIC_START`, `MUSIC_END`, `FIRST_DOWNBEAT`, `INTRO_LENGTH`, `OUTRO_LENGTH` |
| Yes/no                             | `SILENCE_FOUND`, `TRIMMED`                                   |
| Other                              | `BPM_EXACT`, `TEMPO_CHANGES`                                 |

> [!NOTE]
>
> See: References Tagging for the source materials for tagging conventions used

---

# Proof of concept:

The following tracks were bought used to test the concept:

Set list: 

| **Track Name**                                               | **Artist**                                             | **Album**                               |
| ------------------------------------------------------------ | ------------------------------------------------------ | --------------------------------------- |
| STARSTRUKK (feat. Katy Perry)                                | 3OH!3;Katy Perry                                       | WANT (Deluxe)                           |
| Excuses                                                      | Above & Beyond                                         | We Are All We Need                      |
| Hello (Album Mix)                                            | Above & Beyond                                         | We Are All We Need                      |
| Out Of Time                                                  | Above & Beyond                                         | We Are All We Need                      |
| Quieter Is Louder                                            | Above & Beyond                                         | We Are All We Need                      |
| All Over The World                                           | Above & Beyond Group Therapy;Alex Vargas               | We Are All We Need                      |
| Blue Sky Action                                              | Above & Beyond Group Therapy;Alex Vargas               | We Are All We Need                      |
| Making Plans                                                 | Above & Beyond Group Therapy;Alex Vargas               | We Are All We Need                      |
| Sink The Lighthouse                                          | Above & Beyond Group Therapy;Alex Vargas               | We Are All We Need                      |
| Sticky Fingers                                               | Above & Beyond Group Therapy;Alex Vargas               | We Are All We Need                      |
| Counting Down The Days                                       | Above & Beyond Group Therapy;Gemma Hayes               | We Are All We Need                      |
| Little Something                                             | Above & Beyond Group Therapy;Justine Suissa            | We Are All We Need                      |
| Fly To New York                                              | Above & Beyond;Zoë Johnston                            | We Are All We Need                      |
| Peace Of Mind                                                | Above & Beyond;Zoë Johnston                            | We Are All We Need                      |
| Save Me                                                      | Above & Beyond;Zoë Johnston                            | We Are All We Need                      |
| Treasure                                                     | Above & Beyond;Zoë Johnston                            | We Are All We Need                      |
| We're All We Need                                            | Above & Beyond;Zoë Johnston                            | We Are All We Need                      |
| Blankensee (Markus Schulz In Search of Sunrise Rework)       | Ad Astra;Yelow                                         | In Search of Sunrise 16                 |
| In Search of Sunrise                                         | Adina Butar;Markus Schulz                              | In Search of Sunrise 16                 |
| Don't Say Goodbye                                            | Ahmed Romel;Roxanne Emery                              | In Search of Sunrise 16                 |
| I Die (Josh Ferrin Chillout Remix)                           | Alan Morris;Dennis Sheperd;Sue McLaren                 | In Search of Sunrise 16                 |
| Heroes (we could be)                                         | Alesso;Tove Lo                                         | Forever                                 |
| Matière Noire (feat. Alice Evermore)                         | Alice Evermore;Charlotte de Witte                      | Charlotte de Witte                      |
| Empire State Of Mind                                         | Alicia Keys;JAŸ-Z                                      | The Blueprint 3                         |
| If You Only Knew                                             | Amber Revival;Hel:sløwed                               | If You Only Knew                        |
| It Can't Rain for Ever                                       | Andrea Mazza                                           | In Search of Sunrise 16                 |
| Something I Can Dream About (OnAir Mix)                      | April Bender;Giuseppe Ottaviani                        | Horizons [Part 3]                       |
| Something I Can Dream About                                  | April Bender;Giuseppe Ottaviani                        | Horizons [Part 1]                       |
| Are You Out There                                            | Arkham Knights                                         | In Search of Sunrise 16                 |
| In 10 Years From Now                                         | Armin Van Buuren                                       | Intense                                 |
| Last Stop Before Heaven                                      | Armin Van Buuren                                       | Intense                                 |
| Pulsar                                                       | Armin Van Buuren                                       | Intense                                 |
| Who's Afraid Of 138?!                                        | Armin Van Buuren                                       | Intense                                 |
| Won't Let You Go                                             | Armin Van Buuren;Aruna                                 | Intense                                 |
| Reprise                                                      | Armin Van Buuren;Bagga Bownz                           | Intense                                 |
| Beautiful Life (Extended Mix)                                | Armin Van Buuren;Cindy Alma                            | Intense                                 |
| Forever Is Ours                                              | Armin Van Buuren;Emma Hewitt                           | Intense                                 |
| Waiting For The Night                                        | Armin Van Buuren;FIORA                                 | Intense                                 |
| Sound Of The Drums                                           | Armin Van Buuren;Laura Jansen                          | Intense                                 |
| Turn This Love Around                                        | Armin Van Buuren;Laura V;NERVO                         | Intense                                 |
| Intense                                                      | Armin Van Buuren;Miri Ben-Ari                          | Intense                                 |
| Love Never Came                                              | Armin Van Buuren;Richard Bedford                       | Intense                                 |
| New York City (Escape Mix)                                   | Ashley Tomberlin;Austin Leeds;Paul van Dyk;Starkillers | In Search of Sunrise 16                 |
| Alien Turned Human                                           | Astrix                                                 | He.art                                  |
| Deep Jungle Walk                                             | Astrix                                                 | He.art                                  |
| He.art                                                       | Astrix                                                 | He.art                                  |
| Sapana (album version)                                       | Astrix                                                 | He.art                                  |
| Shamanic Tales                                               | Astrix                                                 | He.art                                  |
| Valley of Stevie                                             | Astrix & Ace Ventura                                   | He.art                                  |
| Agate                                                        | Astrix & Ritmo                                         | He.art                                  |
| Awake the Snake                                              | Astrix & Tristan                                       | He.art                                  |
| The Nights                                                   | Avicii                                                 | The Days / Nights (EP)                  |
| Wake Me Up                                                   | Avicii                                                 | True                                    |
| Without You                                                  | Avicii;Sandro Cavazza                                  | AVĪCI (01)                              |
| Happier                                                      | Bastille;Marshmello                                    | Happier                                 |
| All Over Again (Extended Mix)                                | Bryan Kearney;Plumb                                    | All Over Again                          |
| Everytime We Touch                                           | Cascada                                                | Platinum                                |
| We Don't Talk Anymore (feat. Selena Gomez)                   | Charlie Puth;Selena Gomez                              | Nine Track Mind                         |
| Become                                                       | Charlotte de Witte                                     | Charlotte de Witte                      |
| Domine                                                       | Charlotte de Witte                                     | Charlotte de Witte                      |
| Higher                                                       | Charlotte de Witte                                     | Charlotte de Witte                      |
| Hymn                                                         | Charlotte de Witte                                     | Charlotte de Witte                      |
| Memento Mori                                                 | Charlotte de Witte                                     | Charlotte de Witte                      |
| The Realm                                                    | Charlotte de Witte                                     | Charlotte de Witte                      |
| Vidmahe                                                      | Charlotte de Witte                                     | Charlotte de Witte                      |
| The Heads That Know (feat. Comma Dee)                        | Charlotte de Witte;Comma Dee                           | Charlotte de Witte                      |
| After The Fall (feat. Lisa Gerrard)                          | Charlotte de Witte;Lisa Gerrard                        | Charlotte de Witte                      |
| No Division (feat. XSALT)                                    | Charlotte de Witte;XSALT                               | Charlotte de Witte                      |
| Closer (OnAir Mix)                                           | Christian Burns;Giuseppe Ottaviani                     | Horizons [Part 3]                       |
| Closer                                                       | Christian Burns;Giuseppe Ottaviani                     | Horizons [Part 2]                       |
| In Peace (Chill Mix)                                         | Cold Blue                                              | In Search of Sunrise 16                 |
| If This Is True                                              | Cressida                                               | In Search of Sunrise 16                 |
| Levitating (feat. DaBaby)                                    | DaBaby;Dua Lipa                                        | Levitating (feat. DaBaby)               |
| Hero (OnAir Mix)                                             | Dan Soleil;Giuseppe Ottaviani                          | Horizons [Part 3]                       |
| Hero                                                         | Dan Soleil;Giuseppe Ottaviani                          | Horizons [Part 1]                       |
| Once in a Lifetime (I Found Sunrise Mix)                     | Daniel Wanrooy                                         | In Search of Sunrise 16                 |
| A Glimmer of Hope                                            | Dave Neven;Ocata                                       | In Search of Sunrise 16                 |
| Titanium (feat. Sia)                                         | David Guetta;Sia                                       | Nothing but the Beat (Ultimate Edition) |
| Without You (feat. Usher)                                    | David Guetta;Usher                                     | Nothing but the Beat (Ultimate Edition) |
| While We Wait                                                | Daxson                                                 | In Search of Sunrise 16                 |
| Aural Psynapse                                               | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Brazil (2nd Edit)                                            | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Ghosts 'N' Stuff (Chuckie Remix)                             | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Ghosts 'N' Stuff (Nero Remix)                                | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Ghosts 'N' Stuff                                             | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| I Remember (Shiba San Remix)                                 | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| I Remember                                                   | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Maths (Botnek Remix)                                         | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Not Exactly                                                  | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Raise Your Weapon (Madeon Remix)                             | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Raise Your Weapon (Wax Motif Remix)                          | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Raise Your Weapon                                            | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Sofi Needs A Ladder (Pig&Dan Remix)                          | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Sofi Needs A Ladder                                          | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Some Chords (Dillon Francis Remix)                           | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Some Chords                                                  | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| Strobe (Michael Woods 2014 Remix)                            | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| Strobe                                                       | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| The Veldt (Deadmau5 Vs. Eric Prydz Edit)                     | Deadmau5                                               | 5 Years Of Mau5 (2)                     |
| The Veldt                                                    | Deadmau5                                               | 5 Years Of Mau5 (1)                     |
| I Can Feel (Chillout Mix)                                    | Dennis Sheperd;Sunlounger                              | In Search of Sunrise 16                 |
| Stealing Time (Markus Schulz In Search of Sunrise Rework)    | Dj T.H.;Jan Johnston                                   | In Search of Sunrise 16                 |
| Butterflies                                                  | Dj T.H.;Linnea Schössow;Manuel Le Saux                 | In Search of Sunrise 16                 |
| Scared to Be Lonely                                          | Dua Lipa;Martin Garrix                                 | Scared to Be Lonely                     |
| Falcon                                                       | Francesco Sambero;Madeleine Wood                       | In Search of Sunrise 16                 |
| 8k (Chillout Super Extended Mix)                             | Giuseppe Ottaviani                                     | In Search of Sunrise 16                 |
| Celsius (OnAir Mix)                                          | Giuseppe Ottaviani                                     | Horizons [Part 3]                       |
| Celsius                                                      | Giuseppe Ottaviani                                     | Horizons [Part 2]                       |
| Fahrenheit (OnAir Mix)                                       | Giuseppe Ottaviani                                     | Horizons [Part 3]                       |
| Fahrenheit                                                   | Giuseppe Ottaviani                                     | Horizons [Part 1]                       |
| Spellbound                                                   | Giuseppe Ottaviani                                     | In Search of Sunrise 16                 |
| Sundown                                                      | Giuseppe Ottaviani                                     | In Search of Sunrise 16                 |
| The Wind in Your Face (OnAir Mix)                            | Giuseppe Ottaviani                                     | Horizons [Part 3]                       |
| The Wind in Your Face                                        | Giuseppe Ottaviani                                     | Horizons [Part 1]                       |
| Under Dark Skies                                             | Giuseppe Ottaviani                                     | Horizons [Part 2]                       |
| Tree of Souls                                                | Giuseppe Ottaviani;Hypaton                             | Horizons [Part 1]                       |
| Colour Me (OnAir Mix)                                        | Giuseppe Ottaviani;Jan Burton                          | Horizons [Part 3]                       |
| Colour Me                                                    | Giuseppe Ottaviani;Jan Burton                          | Horizons [Part 1]                       |
| Silhouettes & Outlines (OnAir Mix)                           | Giuseppe Ottaviani;Jess Ball                           | Horizons [Part 3]                       |
| Silhouettes & Outlines                                       | Giuseppe Ottaviani;Jess Ball                           | Horizons [Part 2]                       |
| Bittersweet                                                  | Giuseppe Ottaviani;Katrine Stenbekk                    | Horizons [Part 2]                       |
| Fade Away (OnAir Mix)                                        | Giuseppe Ottaviani;Mila Josef                          | Horizons [Part 3]                       |
| Fade Away                                                    | Giuseppe Ottaviani;Mila Josef                          | Horizons [Part 1]                       |
| With You (OnAir Mix)                                         | Giuseppe Ottaviani;Monika Santucci                     | Horizons [Part 3]                       |
| With You                                                     | Giuseppe Ottaviani;Monika Santucci                     | Horizons [Part 1]                       |
| Replay (OnAir Mix)                                           | Giuseppe Ottaviani;Natalie Shay                        | Horizons [Part 3]                       |
| Replay                                                       | Giuseppe Ottaviani;Natalie Shay                        | Horizons [Part 1]                       |
| Keep You Safe (OnAir Mix)                                    | Giuseppe Ottaviani;Richard Walters                     | Horizons [Part 3]                       |
| Keep You Safe                                                | Giuseppe Ottaviani;Richard Walters                     | Horizons [Part 2]                       |
| Melody (OnAir Mix)                                           | Giuseppe Ottaviani;Sarah de Warren                     | Horizons [Part 3]                       |
| Melody                                                       | Giuseppe Ottaviani;Sarah de Warren                     | Horizons [Part 2]                       |
| Freedom (OnAir Mix)                                          | Giuseppe Ottaviani;Sue McLaren                         | Horizons [Part 3]                       |
| Freedom                                                      | Giuseppe Ottaviani;Sue McLaren                         | Horizons [Part 2]                       |
| Not One Goodbye                                              | Giuseppe Ottaviani;Sue McLaren                         | In Search of Sunrise 16                 |
| Won't Matter Much (OnAir Mix)                                | Giuseppe Ottaviani;Treetalk                            | Horizons [Part 3]                       |
| Won't Matter Much                                            | Giuseppe Ottaviani;Treetalk                            | Horizons [Part 2]                       |
| Afterglow (Kryder Remix)                                     | Grum;Natalie Shay                                      | In Search of Sunrise 16                 |
| Feel Good                                                    | Gryffin;Illenium;daya                                  | Feel Good                               |
| Without Me                                                   | Halsey;Juice Wrld                                      | Manic                                   |
| Be Kind                                                      | Halsey;Marshmello                                      | Be Kind                                 |
| Fall Again                                                   | HAYLA                                                  | Fall Again                              |
| Take Me With You                                             | Hydra;The Thrillseekers                                | In Search of Sunrise 16                 |
| No Man's Sky                                                 | Hypaton                                                | In Search of Sunrise 16                 |
| Good Things Fall Apart                                       | Illenium;Jon Bellion                                   | Good Things Fall Apart                  |
| Tuvalu                                                       | IONA COAST                                             | In Search of Sunrise 16                 |
| Thorium-238                                                  | Isotapes;NOMADsignal                                   | In Search of Sunrise 16                 |
| Balearic Reflection (Markus Schulz In Search of Sunrise Intro Mix) | Johan Gielen                                           | In Search of Sunrise 16                 |
| SHADES OF BLUE                                               | John Summit; Devault; Julia Church                     | CTRL ESCAPE                             |
| Shiver                                                       | John Summit; HAYLA                                     | Comfort In Chaos                        |
| Where You Are                                                | John Summit; HAYLA                                     | Comfort In Chaos                        |
| palm of my hands                                             | John Summit; venbee                                    | Comfort In Chaos                        |
| Conquistador (Astrix remix)                                  | Juno Reactor                                           | He.art                                  |
| The One That Got Away (Acoustic)                             | Katy Perry                                             | Teenage Dream: The Complete Confection  |
| The One That Got Away                                        | Katy Perry                                             | Teenage Dream: The Complete Confection  |
| If We Ever Meet Again (Featuring Katy Perry)                 | Katy Perry;Timbaland                                   | Shock Value II                          |
| Stroller Symphony (Markus Schulz In Search of Sunrise Rework) | Kris O’Neil                                            | In Search of Sunrise 16                 |
| Empty Streets (Markus Schulz In Search of Sunrise Remix)     | Late Night Alumni                                      | In Search of Sunrise 16                 |
| Carrying the Fire                                            | Madis                                                  | In Search of Sunrise 16                 |
| Animus                                                       | Manuel Le Saux                                         | In Search of Sunrise 16                 |
| Fragile (Ambienced)                                          | Marco Torrance;Natasha Jaffe                           | In Search of Sunrise 16                 |
| Payphone                                                     | Maroon 5;Wiz Khalifa                                   | Overexposed (Deluxe)                    |
| Bliss (Chillout Mix)                                         | Melodia;Pierre Pienaar                                 | In Search of Sunrise 16                 |
| Midnight Colours                                             | Mike EFEX                                              | In Search of Sunrise 16                 |
| Save the World (Sunlounger Remix)                            | Natalie Gioia;Roger Shah                               | In Search of Sunrise 16                 |
| Birthright (Danijel Kostic Remix Edit)                       | Nora En Pure                                           | Birthright (The Remixes)                |
| Birthright (Danijel Kostic Remix)                            | Nora En Pure                                           | Birthright (The Remixes)                |
| Birthright (Dosem Remix Edit)                                | Nora En Pure                                           | Birthright (The Remixes)                |
| Birthright (Dosem Remix)                                     | Nora En Pure                                           | Birthright (The Remixes)                |
| Birthright (Marius Drescher Remix Edit)                      | Nora En Pure                                           | Birthright (The Remixes)                |
| Birthright (Marius Drescher Remix)                           | Nora En Pure                                           | Birthright (The Remixes)                |
| Branches (Original Club Mix)                                 | Nora En Pure                                           | Don't Look Back EP                      |
| Branches                                                     | Nora En Pure                                           | Don't Look Back EP                      |
| Caught in the Act (Original Club Mix)                        | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Caught in the Act                                            | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Diving with Whales (Extended Mix)                            | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Diving with Whales                                           | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Don't Look Back (Extended Mix)                               | Nora En Pure                                           | Don't Look Back EP                      |
| Don't Look Back                                              | Nora En Pure                                           | Don't Look Back EP                      |
| Dry Sobbing (Original Club Mix)                              | Nora En Pure                                           | Homebound EP                            |
| Dry Sobbing                                                  | Nora En Pure                                           | Homebound EP                            |
| Epiphany (Original Club Mix)                                 | Nora En Pure                                           | Homebound EP                            |
| Epiphany                                                     | Nora En Pure                                           | Homebound EP                            |
| Freedom Lives Within (Chillout Texture)                      | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Freedom Lives Within (Original Club Mix)                     | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Freedom Lives Within                                         | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Harvesting (Club Mix)                                        | Nora En Pure                                           | Polynesia EP                            |
| Harvesting                                                   | Nora En Pure                                           | Polynesia EP                            |
| Homebound (Original Club Mix)                                | Nora En Pure                                           | Homebound EP                            |
| Homebound                                                    | Nora En Pure                                           | Homebound EP                            |
| Lioness (Club Mix)                                           | Nora En Pure                                           | Polynesia EP                            |
| Lioness                                                      | Nora En Pure                                           | Polynesia EP                            |
| Make Me Love You (Original Club Mix)                         | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Make Me Love You                                             | Nora En Pure                                           | Conquer Yosemite - EP                   |
| Polynesia (Extended Mix)                                     | Nora En Pure                                           | Polynesia EP                            |
| Polynesia                                                    | Nora En Pure                                           | Polynesia EP                            |
| Riverwards Stream (Extended Mix)                             | Nora En Pure                                           | Polynesia EP                            |
| Riverwards Stream                                            | Nora En Pure                                           | Polynesia EP                            |
| Roots (Original Club Mix)                                    | Nora En Pure                                           | Don't Look Back EP                      |
| Roots                                                        | Nora En Pure                                           | Don't Look Back EP                      |
| drivers license                                              | Olivia Rodrigo                                         | SOUR                                    |
| good 4 u                                                     | Olivia Rodrigo                                         | SOUR                                    |
| traitor                                                      | Olivia Rodrigo                                         | SOUR                                    |
| Away from Me                                                 | Pavel Khvaleev;Sopheary                                | In Search of Sunrise 16                 |
| Into This Galaxy                                             | Peter Santos                                           | In Search of Sunrise 16                 |
| Karma                                                        | Peter Steele                                           | In Search of Sunrise 16                 |
| All We Know (feat. Phoebe Ryan)                              | Phoebe Ryan;The Chainsmokers                           | All We Know (feat. Phoebe Ryan)         |
| Melodrama                                                    | Purple Stories                                         | In Search of Sunrise 16                 |
| A Life Time Away                                             | Rich TriPhonic                                         | In Search of Sunrise 16                 |
| Dandelions                                                   | Ruth B.                                                | Safe Haven                              |
| Shimmer of Tides                                             | Sean;Xander                                            | In Search of Sunrise 16                 |
| 742617000027                                                 | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| (sic) [Molt-Injected Mix]                                    | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| (sic)                                                        | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Despise (Demo)                                               | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Diluted                                                      | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Eeyore                                                       | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Eyeless                                                      | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Get This                                                     | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Interloper (Demo)                                            | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Liberate                                                     | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Me Inside                                                    | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| No Life                                                      | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Only One                                                     | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Prosthetics                                                  | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Purity                                                       | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Scissors                                                     | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Snap (Demo)                                                  | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Spit It Out (Hyper Version)                                  | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Spit It Out (Stamp You out Mix)                              | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Spit It Out                                                  | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Surfacing                                                    | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Tattered & Torn                                              | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Wait and Bleed (Demo)                                        | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Wait and Bleed (Terry Date Mix)                              | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| Wait and Bleed                                               | Slipknot                                               | Slipknot (10th Anniversary Edition)     |
| New Horizons                                                 | Starpicker                                             | In Search of Sunrise 16                 |
| Super Nature (Chillout Mix)                                  | Stoneface;Terminal                                     | In Search of Sunrise 16                 |
| Hello Sunrise (Chillout Mix)                                 | Sunlounger                                             | In Search of Sunrise 16                 |
| you broke me first                                           | Tate McRae                                             | you broke me first                      |
| Blank Space                                                  | Taylor Swift                                           | 1989                                    |
| I Knew You Were Trouble.                                     | Taylor Swift                                           | Red                                     |
| Paris                                                        | The Chainsmokers                                       | Paris                                   |
| Don't Let Me Down                                            | The Chainsmokers;daya                                  | Don't Let Me Down                       |
| Iris                                                         | The Goo Goo Dolls                                      | Greatest Hits Volume One - The Singles  |
| This Is All We Have (Sunset Mix Edit)                        | The Thrillseekers                                      | In Search of Sunrise 16                 |
| Gratitude (Chillout Mix)                                     | Thomas Benscher                                        | In Search of Sunrise 16                 |
| You & I (Sunlounger Remix)                                   | Yelow                                                  | In Search of Sunrise 16                 |



## Post Processing Results: 

> [!NOTE]
>
> See attached: Processed.xls

# Technical

## Minimum hardware specs

This program was developed and tested on the following hardware and OS

- CPU: Intel Core i7-7700K
- GPU: NVIDIA GeForce RTX 2060
- RAM 32 GB
- OS: Ubuntu 24.04

> [!NOTE]
>
> This program is able to run on CPU alone, but it recommended to have GPU, but it might be painfully slow
> GPU Measured peak use: about 1 GB of video memory



## Installation

### System Packages: 

1. FFmpeg
   ` sudo apt install ffmpeg`

2. rsgain

   `sudo apt install rsgain`

   

3. Python => 3.12
   refer to official python installation steps

4. CUDA
   refer to official CUDA installation steps

## Program Installation

1. Clone Repo:
2. Create And Activate Python Virtual Enviroment
3. Test:
   1. Test Your GPU
   2. Test on one track in dry-run mode

## Running the program

### Run on whole libary, do not touch the orginal tracks and output to a seperate directorty: 
`python3 main.py --input $locationOfYourOrginalTracks --output-directory $locationToStoreTheProcessedTracks`

### Run on whole libary, directly add the metadaya to the track's metadata
`python3 main.py --input $locationOfYourOrginalTracks --overwrite`

### Run on a large Libary: 

*I am not a big fan of tmux*

- Run the process:
`nohup nice -n 10 python3 main.py --input $locationOfYourOrginalTracks --output-directory $locationOfYourOrginalTracks --log-file ~/Tracks/run.log > /dev/null 2>&1 &`

- Watch the log file:
`tail -f run.log

### Report Generation



### CLI Options: 

| **Option**               | **What it does**                                             |
| ------------------------ | ------------------------------------------------------------ |
| `--input PATH`           | **Required.** One track, or a folder of tracks               |
| `--recursive`            | Also process tracks in subfolders. The folder structure is kept in the output directory. |
| `--trim-silence`         | Removes leading and trailing silence. Without it, silence is only measured and tagged. |
| `--silence-threshold DB` | How quiet counts as silence. Default: `-60`                  |
| `--only STEPS`           | Runs only the steps you list, separated by commas, for example `tempo,key`. Steps that depend on others run what they need. |
| `--skip-analysed`        | Skips tracks that already have an `ENERGY` tag               |
| `--dry-run`              | Analyses and prints the results, but writes nothing          |
| `--limit N`              | Processes only the first N tracks                            |
| `--random`               | Processes tracks in random order. With `--limit`: a random sample of N tracks. |
| `--log-file FILE`        | Saves the log and the summary to a file                      |
| `--debug STEP=LEVEL`     | Extra output for one step, level 1 (least) to 5 (most). Repeat it, or separate with commas. Use `all=N` for every step. |







# References

## Tagging

- ID3 Tags
  Reference: ID3 tag version 2.4.0 - Main Structure
  URL: https://id3.org/id3v2.4.0-structure

- TagLib

  - Reference: TagLib API Documentation

    URL: https://taglib.org/api/

## Further Reading:



