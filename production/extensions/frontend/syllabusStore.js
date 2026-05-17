import { writable } from 'svelte/store';

// ── Existing store ────────────────────────────────────────────────────────────
// Holds metadata for the next chat to be created.
// Written by LessonCardPanel / SyllabusNode; consumed by HistoryTracker.
export const pendingSyllabusTag = writable(null);

// ── BreadcrumbBar selection state ─────────────────────────────────────────────
// null  = nothing selected (BreadcrumbBar shows all dropdowns at root)
// Shape when set:
//   {
//     pathKeys:   string[]   — folder-name path from the tree root
//                             e.g. ['CSIR_Chemical_Sciences','CHEM100','inorganic_chemistry','chemical_periodicity']
//     pathLabels: string[]   — human-readable labels for the breadcrumb display
//                             e.g. ['CSIR Chemical Sciences','CHEM100','Inorganic Chemistry','Chemical Periodicity']
//     folderKey:  string     — stable identifier from _meta.folder_key at the course level
//                             e.g. 'chem100'  (used for entitlement checks)
//     files:      object[]   — _files array from the selected topic folder
//                             each: { filename, metadata: {lesson,concept,clarification}, links: [{label,data}] }
//   }
export const selectedTopic = writable(null);

// ── Entitlement cache ─────────────────────────────────────────────────────────
// Populated lazily by LessonCardPanel on first Show click per folder_key.
// Never cleared during the session — entitlements don't change mid-session.
// Shape: { [folder_key]: 'allowed' | 'blocked' | 'expired' }
export const entitlements = writable({});

// ── Study panel visibility ────────────────────────────────────────────────────
// true  = Study Materials modal is open
// false = closed
// Set to false by generateNotes() before navigating to a chat.
export const studyPanelOpen = writable(false);
