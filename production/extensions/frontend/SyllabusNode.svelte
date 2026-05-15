<script>
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { showSidebar, mobile, user, chatId } from '$lib/stores';
	import { pendingSyllabusTag } from './syllabusStore.js';

	export let tree = {};
	export let depth = 0;

	const getFolderKeys = (obj) => {
		return Object.keys(obj)
			.filter((k) => k !== '_files')
			.sort();
	};

	/**
	 * Fetches a prompt template from the backend, substitutes variables, and returns the final prompt.
	 * Resolution: per-exam override → global default → hardcoded fallback (backend handles this).
	 */
	const buildPrompt = async (functionName, vars) => {
		const examParam = vars.EXAM ? `?exam=${encodeURIComponent(vars.EXAM)}` : '';
		try {
			const res = await fetch(`/api/ext/syllabus/prompts/${functionName}${examParam}`);
			if (res.ok) {
				let template = await res.text();
				// Substitute all {VAR_NAME} placeholders
				for (const [key, value] of Object.entries(vars)) {
					template = template.replaceAll(`{${key}}`, value || '');
				}
				return template;
			}
		} catch (e) {
			console.error('[Ext] Failed to fetch prompt template:', e);
		}
		// Ultimate fallback: minimal prompt if API is unreachable
		return `You are an expert tutor for ${vars.SUBJECT || 'this topic'}.\nTopic: ${vars.TOPIC}\nFocus: ${vars.CONCEPT}\nGenerate study material.`;
	};

	// Identity tuple used by the Smart Router cache. Two clicks resolve to the same
	// chat ONLY when every field below matches. MCQ links share concept + data_function
	// across difficulty levels, so `level` (and `number`) MUST participate in the key.
	const norm = (v) => (v == null ? '' : String(v));
	const cacheKey = (t) =>
		[
			norm(t.data_function),
			norm(t.exam),
			norm(t.subject),
			norm(t.topic),
			norm(t.lesson),
			norm(t.concept),
			norm(t.level),
			norm(t.number)
		].join('||');

	const generateNotes = async (linkData, metadata, linkLabel) => {
		// Build the identity for THIS click from data-* attributes + lesson metadata.
		const clickIdentity = {
			data_function: linkData.function,
			exam: linkData.exam || 'General',
			subject: linkData.subject || 'General',
			topic: linkData.topic || 'General',
			lesson: linkData.lesson || 'General',
			concept: metadata.concept || '',
			level: linkData.level || '',
			number: linkData.number || ''
		};
		const clickKey = cacheKey(clickIdentity);

		// 1. "Smart Router" Cache Check
		if ($user) {
			try {
				const res = await fetch(`/api/ext/history/tags/${$user.id}`);
				if (res.ok) {
					const data = await res.json();
					const tags = data.tags || [];
					const existing = tags.find((t) => cacheKey(t) === clickKey);

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
		// Capture the chat id and pathname AT CLICK TIME so HistoryTracker can
		// distinguish "this is the pre-existing chat I clicked from" (must NOT
		// be tagged) from "this is the freshly created chat for this generation"
		// (must be tagged). Without this, when the user clicks from
		// /c/<existing>, $chatId still holds the existing id for a brief window
		// after the tag is set and before /?q=... navigation resets it — the
		// reactive block in HistoryTracker would otherwise POST the metadata
		// onto the existing chat.
		const originChatId = get(chatId) || '';
		const originPathname = get(page)?.url?.pathname || '';
		const requestId =
			(typeof crypto !== 'undefined' && crypto.randomUUID)
				? crypto.randomUUID()
				: `syl-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

		// Store metadata so HistoryTracker can tag it when URL changes
		pendingSyllabusTag.set({
			function: clickIdentity.data_function,
			exam: clickIdentity.exam,
			subject: clickIdentity.subject,
			topic: clickIdentity.topic,
			lesson: clickIdentity.lesson,
			concept: clickIdentity.concept,
			level: clickIdentity.level,
			number: clickIdentity.number,
			// Race-guard fields (consumed only by HistoryTracker):
			originChatId,
			originPathname,
			requestId,
			createdAt: Date.now()
		});

		// 3. Build the prompt from external template
		const templateVars = {
			EXAM: linkData.exam || '',
			SUBJECT: linkData.subject || 'this topic',
			TOPIC: linkData.topic || metadata.lesson || '',
			CONCEPT: metadata.concept || '',
			CLARIFICATION: metadata.clarification || '',
			LINK_LABEL: linkLabel || '',
			NUM_QUESTIONS: String(linkData.number || 5),
			LEVEL: linkData.level || 'basic'
		};

		const promptText = await buildPrompt(linkData.function, templateVars);
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
