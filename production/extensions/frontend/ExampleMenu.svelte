<script>
    import { goto } from '$app/navigation';
    import { getContext } from 'svelte';
    const i18n = getContext('i18n');
</script>

<div class="px-2 mt-0.5">
    <details class="group">
        <summary class="flex items-center space-x-2 px-2.5 py-1.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-900 transition cursor-pointer outline-none select-none text-gray-800 dark:text-gray-200">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4 text-gray-500">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span class="text-sm font-medium">Extra Resources</span>
        </summary>
        <div class="ml-4 pl-2 mt-1 border-l border-gray-200 dark:border-gray-800 space-y-1 pb-1">
            <button on:click={() => window.open('#', '_blank')} class="w-full text-left px-2 py-1.5 text-[12px] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800 rounded transition">
                Platform Guide
            </button>
            <button on:click={() => window.open('https://blog.examcatalyst.ai', '_blank')} class="w-full text-left px-2 py-1.5 text-[12px] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800 rounded transition">
                PYQ Blog
            </button>
            <button on:click={() => window.open('https://notes.examcatalyst.ai', '_blank')} class="w-full text-left px-2 py-1.5 text-[12px] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800 rounded transition">
                PYQ Notes
            </button>
        </div>
    </details>
</div>
