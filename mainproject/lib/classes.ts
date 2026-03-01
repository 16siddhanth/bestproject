// Shared list of vegetable waste classes used by both API routes and other modules.
// If you update this list, both /api/classes and the classification adapter will reflect it.
export const vegetableClasses = [
  "Carrot Peels",
  "Potato Skins",
  "Lettuce",
  "Cabbage Leaves",
  "Onion Skins",
  "Tomato Skins",
  "Cucumber Peels",
  "Bell Pepper Scraps",
  "Broccoli Stems",
  "Cauliflower Leaves",
  "Celery",
  "Spinach",
] as const

export type VegetableClass = (typeof vegetableClasses)[number]
