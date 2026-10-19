// Section titles around a recap, in the language the recap is written in.
// Mirrors api/app/recap_labels.py (which labels the reminders).

export interface RecapLabels {
  keyPoints: string
  formulas: string
  exercises: string
  beforeNextLesson: string
}

const ENGLISH: RecapLabels = {
  keyPoints: 'Key points',
  formulas: 'Formulas',
  exercises: 'Exercises',
  beforeNextLesson: 'Before next lesson',
}

// Serbian recaps are written in Cyrillic.
const SERBIAN: RecapLabels = {
  keyPoints: 'Најважније',
  formulas: 'Формуле',
  exercises: 'Вежбе',
  beforeNextLesson: 'Пре следећег часа',
}

const LABELS: Record<string, RecapLabels> = {
  english: ENGLISH,
  serbian: SERBIAN,
  srpski: SERBIAN,
  српски: SERBIAN,
}

export function recapLabels(language: string | null | undefined): RecapLabels {
  return LABELS[(language ?? '').trim().toLowerCase()] ?? ENGLISH
}
