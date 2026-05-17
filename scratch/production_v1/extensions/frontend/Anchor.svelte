<script>
    import SyllabusSidebarMenu from './SyllabusSidebarMenu.svelte';
    import CategorizedHistory from './CategorizedHistory.svelte';
    import HistoryTracker from './HistoryTracker.svelte';
    import ExampleMenu from './ExampleMenu.svelte';

    let activeTab = 'syllabus'; // 'syllabus' or 'history'
</script>

<div class="custom-extensions-anchor pb-2">
    <!-- Headless Tracker for Syllabus tagging (renders nothing) -->
    <HistoryTracker />

    <!-- Tab Selector -->
    <div class="flex mx-2 mt-1 mb-1 bg-gray-100 dark:bg-gray-850 rounded-lg p-0.5">
        <button
            on:click={() => activeTab = 'syllabus'}
            class="flex-1 text-[11px] font-medium py-1.5 rounded-md transition-all
                {activeTab === 'syllabus'
                    ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
        >
            📚 Syllabus
        </button>
        <button
            on:click={() => activeTab = 'history'}
            class="flex-1 text-[11px] font-medium py-1.5 rounded-md transition-all
                {activeTab === 'history'
                    ? 'bg-white dark:bg-gray-800 text-purple-600 dark:text-purple-400 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
        >
            📋 History
        </button>
    </div>

    <!-- Tab Content -->
    <div class="overflow-y-auto">
        {#if activeTab === 'syllabus'}
            <SyllabusSidebarMenu />
        {:else}
            <CategorizedHistory />
        {/if}
    </div>

    <!-- Extra Resources -->
    <ExampleMenu />
</div>
