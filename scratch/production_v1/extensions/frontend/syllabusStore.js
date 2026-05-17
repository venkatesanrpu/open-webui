import { writable } from 'svelte/store';

// Holds the metadata for the next chat to be created
export const pendingSyllabusTag = writable(null);
