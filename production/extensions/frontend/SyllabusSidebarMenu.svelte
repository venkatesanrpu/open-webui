<script>
    import { onMount } from 'svelte';
    import SyllabusNode from './SyllabusNode.svelte';

    let syllabusTree = {};
    let error = null;

    onMount(async () => {
        try {
            // trial-index returns only always_active plan content —
            // visible to all users without entitlement checks.
            const response = await fetch('/api/ext/syllabus/trial-index');
            if (response.ok) {
                syllabusTree = await response.json();
            } else {
                error = 'Failed to load trial content';
            }
        } catch (e) {
            error = e.message;
        }
    });
</script>

<div class="px-2 mt-0.5">
    {#if error}
        <p class="text-[11px] text-red-500 px-2 py-1 bg-red-50 dark:bg-red-900/20 rounded">{error}</p>
    {:else if Object.keys(syllabusTree).length === 0}
        <!-- Loading / empty state — silent, no spinner needed for the sidebar -->
    {:else}
        <details class="group" open>
            <summary class="flex items-center space-x-2 px-2.5 py-1.5 rounded-xl
                            hover:bg-gray-100 dark:hover:bg-gray-900 transition
                            cursor-pointer outline-none select-none
                            text-gray-800 dark:text-gray-200">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                     stroke-width="2" stroke="currentColor" class="size-4 text-blue-500">
                    <path stroke-linecap="round" stroke-linejoin="round"
                          d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                </svg>
                <span class="text-sm font-medium">Trial Study Materials</span>
            </summary>

            <div class="mt-1 border-gray-200 dark:border-gray-800">
                <SyllabusNode tree={syllabusTree} depth={0} />
            </div>
        </details>
    {/if}
</div>
