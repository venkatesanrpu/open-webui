<script>
    import { studyPanelOpen } from './syllabusStore.js';
    import BreadcrumbBar from './BreadcrumbBar.svelte';
    import LessonCardPanel from './LessonCardPanel.svelte';

    /**
     * Portal action — moves the node to document.body so that position:fixed
     * is always relative to the viewport, regardless of whether the sidebar
     * parent uses CSS transform (Open WebUI slide animation).
     * Without this, a parent transform creates a new containing block and
     * breaks fixed positioning.
     */
    function portal(node) {
        document.body.appendChild(node);
        return {
            destroy() {
                try { document.body.removeChild(node); } catch (_) {}
            }
        };
    }
</script>

<!--
    StudyPanel — full-viewport modal for Study Materials navigation.

    Mounted inside Anchor.svelte (sidebar) but rendered via the portal action
    at document.body level, so position:fixed always covers the full viewport.

    Layout:
      ┌─────────────────────────────────────────┐
      │  Study Materials                      × │  ← header
      ├─────────────────────────────────────────┤
      │  [Exam ▼] › [Course ▼] › ...  [Show]   │  ← BreadcrumbBar
      ├─────────────────────────────────────────┤
      │  Lesson cards (appears after Show)       │  ← LessonCardPanel
      └─────────────────────────────────────────┘

    Closes when:
      • × button clicked
      • Backdrop clicked (outside the panel card)
      • Escape key pressed
      • generateNotes() is called (navigating to a chat)
-->

<svelte:window on:keydown={(e) => { if (e.key === 'Escape') studyPanelOpen.set(false); }} />

{#if $studyPanelOpen}
<div
    use:portal
    class="fixed inset-0 z-[200] flex items-start justify-center
           bg-black/50 pt-16 px-4 pb-8"
    role="dialog"
    aria-modal="true"
    aria-label="Study Materials"
    on:click|self={() => studyPanelOpen.set(false)}
>

    <!-- Panel card -->
    <div class="w-full max-w-2xl flex flex-col
                bg-white dark:bg-gray-900
                rounded-xl shadow-2xl overflow-hidden
                border border-gray-200 dark:border-gray-700
                max-h-[80vh]">

        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-2.5 flex-shrink-0
                    bg-gray-50 dark:bg-gray-850
                    border-b border-gray-200 dark:border-gray-700">
            <div class="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                     stroke-width="2" stroke="currentColor"
                     class="size-4 text-blue-500 flex-shrink-0">
                    <path stroke-linecap="round" stroke-linejoin="round"
                          d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                </svg>
                <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
                    Study Materials
                </span>
            </div>
            <button
                on:click={() => studyPanelOpen.set(false)}
                class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200
                       text-[18px] leading-none transition-colors"
                aria-label="Close study panel"
            >
                ×
            </button>
        </div>

        <!-- Scrollable body: selector row + lesson cards -->
        <div class="overflow-y-auto">
            <BreadcrumbBar />
            <LessonCardPanel />
        </div>
    </div>
</div>
{/if}
