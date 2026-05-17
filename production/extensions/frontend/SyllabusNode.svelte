<script>
	import { generateNotes } from './syllabusUtils.js';

	// ── Props ──────────────────────────────────────────────────────────────────
	export let tree = {};
	export let depth = 0;

	// Path tracking passed down through recursive calls so each leaf knows its
	// full position in the tree.  Root callers (SyllabusSidebarMenu) leave
	// these at their defaults; the recursive <svelte:self> call extends them.
	export let pathKeys   = [];   // e.g. ['Trial', 'trial_chemistry', 'calculus']
	export let pathLabels = [];   // e.g. ['Trial', 'Trial Chemistry', 'Calculus']

	// ── Helpers ────────────────────────────────────────────────────────────────

	/** Return sorted child folder keys, excluding internal _ keys. */
	const getFolderKeys = (obj) =>
		Object.keys(obj)
			.filter((k) => !k.startsWith('_'))
			.sort();

	/** Human-readable label for a folder key at a given depth. */
	const formatName = (name, d) => {
		const clean = name.replace(/_/g, ' ');
		return d === 0 ? clean.toUpperCase() : clean;
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

			<!-- Recursive render — extend the path arrays for each level -->
			<svelte:self
				tree={tree[folder]}
				depth={depth + 1}
				pathKeys={[...pathKeys, folder]}
				pathLabels={[...pathLabels, formatName(folder, depth)]}
			/>
		</details>
	{/each}

	{#if tree._files}
		<div class="space-y-2 mt-1 pb-1">
			{#each tree._files as file}
				<div
					class="bg-gray-50 dark:bg-gray-850/80 rounded p-2.5 border border-gray-100 dark:border-gray-800 shadow-xs"
				>
					{#if file.error}
						<div class="text-[10px] text-red-500">
							Error parsing {file.filename}: {file.error}
						</div>
					{:else}
						<!-- Lesson Name -->
						<div
							class="text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 mb-1 tracking-wider"
						>
							{file.metadata?.lesson || file.filename.replace('.html', '')}
						</div>

						<!-- Concept -->
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

						<!-- Action links — always unlocked in the sidebar (Trial content) -->
						{#if file.links && file.links.length > 0}
							<div
								class="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700/50"
							>
								{#each file.links as link}
									<button
										on:click={() => generateNotes(link.data, file.metadata, link.label)}
										class="text-[10px] font-medium px-2 py-1 bg-white dark:bg-gray-800
											   border border-gray-200 dark:border-gray-700
											   hover:bg-blue-50 dark:hover:bg-blue-900/30
											   hover:border-blue-200 dark:hover:border-blue-800
											   hover:text-blue-600 dark:hover:text-blue-400
											   rounded transition whitespace-nowrap
											   text-gray-700 dark:text-gray-300"
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
