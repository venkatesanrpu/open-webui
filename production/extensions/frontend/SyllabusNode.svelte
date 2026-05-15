<script>
	import { goto } from '$app/navigation';
	import { showSidebar, mobile, user } from '$lib/stores';
	import { pendingSyllabusTag } from './syllabusStore.js';

	export let tree = {};
	export let depth = 0;

	const getFolderKeys = (obj) => {
		return Object.keys(obj)
			.filter((k) => k !== '_files')
			.sort();
	};

	const generateNotes = async (linkData, metadata, linkLabel) => {
		// 1. "Smart Router" Cache Check
		if ($user) {
			try {
				const res = await fetch(`/api/ext/history/tags/${$user.id}`);
				if (res.ok) {
					const data = await res.json();
					const tags = data.tags;
					// Find existing chat for this exact concept and function
					const existing = tags.find(
						(t) => t.concept === metadata.concept && t.data_function === linkData.function
					);

					if (existing) {
						console.log('[Ext] Cache Hit! Re-routing to existing chat:', existing.chat_id);
						goto(`/c/${existing.chat_id}`);
						if ($mobile) showSidebar.set(false);
						return; // Stop here, no new generation
					}
				}
			} catch (e) {
				console.error('Cache lookup failed', e);
			}
		}

		// 2. Cache Miss - Proceed with Generation
		// Store metadata so HistoryTracker can tag it when URL changes
		pendingSyllabusTag.set({
			function: linkData.function,
			exam: linkData.exam || 'General',
			subject: linkData.subject || 'General',
			topic: linkData.topic || 'General',
			lesson: linkData.lesson || 'General',
			concept: metadata.concept
		});

        // Construct the prompt using the data-* attributes and metadata
        let promptText = `You are an expert tutor for ${linkData.subject || 'this topic'}.\n\n`;
        promptText += `Topic: ${linkData.topic || metadata.lesson}\n`;
        promptText += `Focus: ${metadata.concept}\n`;
        if (metadata.clarification) {
            promptText += `Context: ${metadata.clarification}\n\n`;
        }
        
        // Dynamic Task Generation based on the function attribute
        if (linkData.function === 'mcq_widget') {
            const numQuestions = linkData.number || 5;
            const diffLevel = linkData.level || 'basic';
            promptText += `Task: Generate exactly ${numQuestions} multiple-choice questions (MCQs) at a ${diffLevel} difficulty level for this concept. Please provide the answer key and explanations at the end.`;
        } else {
            promptText += `Task: Generate comprehensive ${linkLabel} for this concept.`;
        }

        const query = encodeURIComponent(promptText);
        goto(`/?q=${query}`);
        
        if ($mobile) {
            showSidebar.set(false);
        }
    };

	// Helper to format folder names nicely
	const formatName = (name, d) => {
		const clean = name.replace(/_/g, ' ');
		if (d === 0) return clean.toUpperCase(); // Top level EXAM
		return clean; // capitalize or leave as is
	};
</script>

<div
	class="space-y-0.5 {depth > 0
		? 'ml-3 pl-2 border-l border-gray-100 dark:border-gray-800/50'
		: 'pl-2'}"
>
	{#each getFolderKeys(tree) as folder}
		<details class="group/folder mt-1" open={depth < 1}>
			<summary
				class="text-[12px] {depth === 0
					? 'font-semibold text-gray-800 dark:text-gray-200'
					: 'text-gray-600 dark:text-gray-400'} cursor-pointer hover:text-gray-900 dark:hover:text-white py-1 transition-colors"
			>
				{formatName(folder, depth)}
			</summary>

			<!-- Recursive call to render children -->
			<svelte:self tree={tree[folder]} depth={depth + 1} />
		</details>
	{/each}

	{#if tree._files}
		<div class="space-y-2 mt-1 pb-1">
			{#each tree._files as file}
				<div
					class="bg-gray-50 dark:bg-gray-850/80 rounded p-2.5 border border-gray-100 dark:border-gray-800 shadow-xs"
				>
					{#if file.error}
						<div class="text-[10px] text-red-500">Error parsing {file.filename}: {file.error}</div>
					{:else}
						<!-- Lesson Name -->
						<div
							class="text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 mb-1 tracking-wider"
						>
							{file.metadata?.lesson || file.filename.replace('.html', '')}
						</div>

						<!-- Core / Concept -->
						{#if file.metadata?.concept}
							<div
								class="text-[12px] font-medium text-blue-600 dark:text-blue-400 mb-0.5 leading-snug"
							>
								{file.metadata.concept}
							</div>
						{/if}

						<!-- Clarification -->
						{#if file.metadata?.clarification}
							<div class="text-[11px] text-gray-500 dark:text-gray-400 mb-2 leading-tight">
								{file.metadata.clarification}
							</div>
						{/if}

						<!-- Links (Study Notes | MCQ ...) -->
						{#if file.links && file.links.length > 0}
							<div
								class="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700/50"
							>
								{#each file.links as link}
									<button
										on:click={() => generateNotes(link.data, file.metadata, link.label)}
										class="text-[10px] font-medium px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-200 dark:hover:border-blue-800 hover:text-blue-600 dark:hover:text-blue-400 rounded transition whitespace-nowrap text-gray-700 dark:text-gray-300"
									>
										{link.label}
									</button>
								{/each}
							</div>
						{/if}
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
