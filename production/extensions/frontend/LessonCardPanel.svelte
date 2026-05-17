<script>
    import { selectedTopic, entitlements } from './syllabusStore.js';
    import { generateNotes } from './syllabusUtils.js';

    // ── Access state ───────────────────────────────────────────────────────────
    // 'loading'  — entitlement check in flight
    // 'allowed'  — active subscription (or always_active trial)
    // 'blocked'  — no purchase / not authenticated
    // 'expired'  — subscription lapsed
    let accessState = 'loading';

    // ── Reactive: check entitlement whenever selectedTopic changes ────────────
    $: if ($selectedTopic) {
        checkAccess($selectedTopic.folderKey);
    }

    async function checkAccess(folderKey) {
        if (!folderKey) {
            // Content has no metadata.json → treat as always unlocked
            // (legacy Trial content without folder_key).
            accessState = 'allowed';
            return;
        }

        // Fast path: use cached result from this session.
        const cached = $entitlements[folderKey];
        if (cached) {
            accessState = cached;
            return;
        }

        accessState = 'loading';
        try {
            const res = await fetch(
                `/api/ext/access/check?folder_key=${encodeURIComponent(folderKey)}&action=generate`
            );
            if (res.ok) {
                const data = await res.json();
                // Backend returns 'allowed' | 'blocked' | 'expired'
                accessState = data.result ?? 'blocked';
                // Cache so subsequent Show clicks for the same folder are instant.
                entitlements.update((e) => ({ ...e, [folderKey]: accessState }));
            } else {
                accessState = 'blocked';   // safe default on HTTP error
            }
        } catch (err) {
            console.error('[LessonCardPanel] Access check failed:', err);
            accessState = 'blocked';
        }
    }

    // ── Button click handlers ─────────────────────────────────────────────────

    function handleLockedClick(state) {
        if (state === 'expired') {
            // TODO Phase 3: open renewal/payment modal
            alert('Your subscription has expired. Please renew to continue generating content.');
        } else {
            // TODO Phase 3: open plans/payment modal
            alert('Subscribe to unlock this content and generate AI-powered study notes and MCQs.');
        }
    }

    // ── Label helpers ─────────────────────────────────────────────────────────

    function lockIcon(state) {
        return state === 'expired' ? '↻' : '🔒';
    }

    function lockTitle(state) {
        return state === 'expired' ? 'Renew subscription' : 'Subscribe to unlock';
    }
</script>

<!--
    LessonCardPanel — shows all lesson cards for the topic selected via BreadcrumbBar.

    Rendered immediately below BreadcrumbBar in the main chat pane.
    Hidden (renders nothing) when no topic is selected.

    Each card mirrors the SyllabusNode card layout so the two contexts look
    identical to the user.  The difference is the action buttons:
      - allowed  → normal clickable buttons → generateNotes()
      - blocked  → 🔒 greyed buttons → subscribe prompt
      - expired  → ↻ orange buttons → renewal prompt
      - loading  → dimmed skeleton
-->

{#if $selectedTopic && $selectedTopic.files && $selectedTopic.files.length > 0}
<div class="ext-lesson-panel w-full
            border-b border-gray-200 dark:border-gray-700
            bg-white dark:bg-gray-900
            max-h-72 overflow-y-auto">

    <!-- Panel header: breadcrumb path + close button -->
    <div class="flex items-center justify-between px-3 py-1.5
                border-b border-gray-100 dark:border-gray-800
                bg-gray-50 dark:bg-gray-850 sticky top-0 z-10">
        <span class="text-[10px] font-semibold text-gray-500 dark:text-gray-400 truncate">
            {$selectedTopic.pathLabels.join(' › ')}
        </span>

        <!-- Access state badge -->
        {#if accessState === 'loading'}
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-400">
                checking…
            </span>
        {:else if accessState === 'allowed'}
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 font-medium">
                ✓ unlocked
            </span>
        {:else if accessState === 'expired'}
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-400 font-medium">
                ↻ expired
            </span>
        {:else}
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 font-medium">
                🔒 locked
            </span>
        {/if}

        <!-- Close button -->
        <button
            on:click={() => selectedTopic.set(null)}
            class="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200
                   text-[14px] leading-none transition-colors flex-shrink-0"
            aria-label="Close lesson panel"
        >
            ×
        </button>
    </div>

    <!-- Lesson cards grid -->
    <div class="p-2 flex flex-wrap gap-2">
        {#each $selectedTopic.files as file}
            <div class="flex-1 min-w-[220px] max-w-xs
                        bg-gray-50 dark:bg-gray-850/80 rounded p-2.5
                        border border-gray-100 dark:border-gray-800 shadow-xs">

                {#if file.error}
                    <div class="text-[10px] text-red-500">
                        Error: {file.error}
                    </div>
                {:else}
                    <!-- Lesson name -->
                    <div class="text-[10px] uppercase font-bold
                                text-gray-500 dark:text-gray-400 mb-1 tracking-wider">
                        {file.metadata?.lesson || file.filename.replace('.html', '')}
                    </div>

                    <!-- Concept -->
                    {#if file.metadata?.concept}
                        <div class="text-[12px] font-medium
                                    text-blue-600 dark:text-blue-400 mb-0.5 leading-snug">
                            {file.metadata.concept}
                        </div>
                    {/if}

                    <!-- Clarification -->
                    {#if file.metadata?.clarification}
                        <div class="text-[11px] text-gray-500 dark:text-gray-400 mb-2 leading-tight">
                            {file.metadata.clarification}
                        </div>
                    {/if}

                    <!-- Action buttons -->
                    {#if file.links && file.links.length > 0}
                        <div class="flex flex-wrap gap-1.5 mt-2 pt-2
                                    border-t border-gray-200 dark:border-gray-700/50">
                            {#each file.links as link}
                                {#if accessState === 'allowed'}
                                    <!-- Unlocked: normal clickable button -->
                                    <button
                                        on:click={() => generateNotes(link.data, file.metadata, link.label)}
                                        class="text-[10px] font-medium px-2 py-1
                                               bg-white dark:bg-gray-800
                                               border border-gray-200 dark:border-gray-700
                                               hover:bg-blue-50 dark:hover:bg-blue-900/30
                                               hover:border-blue-200 dark:hover:border-blue-800
                                               hover:text-blue-600 dark:hover:text-blue-400
                                               rounded transition whitespace-nowrap
                                               text-gray-700 dark:text-gray-300"
                                    >
                                        {link.label}
                                    </button>

                                {:else if accessState === 'loading'}
                                    <!-- Loading skeleton -->
                                    <button
                                        disabled
                                        class="text-[10px] font-medium px-2 py-1
                                               bg-gray-100 dark:bg-gray-800
                                               border border-gray-200 dark:border-gray-700
                                               rounded whitespace-nowrap
                                               text-gray-300 dark:text-gray-600
                                               cursor-wait animate-pulse"
                                    >
                                        {link.label}
                                    </button>

                                {:else if accessState === 'expired'}
                                    <!-- Expired: orange renewal button -->
                                    <button
                                        on:click={() => handleLockedClick('expired')}
                                        title={lockTitle(accessState)}
                                        class="text-[10px] font-medium px-2 py-1
                                               bg-white dark:bg-gray-800
                                               border border-orange-300 dark:border-orange-700
                                               hover:bg-orange-50 dark:hover:bg-orange-900/30
                                               text-orange-500 dark:text-orange-400
                                               rounded transition whitespace-nowrap"
                                    >
                                        {lockIcon(accessState)} {link.label}
                                    </button>

                                {:else}
                                    <!-- Blocked/locked: grey lock button -->
                                    <button
                                        on:click={() => handleLockedClick('blocked')}
                                        title={lockTitle(accessState)}
                                        class="text-[10px] font-medium px-2 py-1
                                               bg-gray-50 dark:bg-gray-800
                                               border border-gray-200 dark:border-gray-700
                                               text-gray-400 dark:text-gray-500
                                               rounded whitespace-nowrap
                                               cursor-pointer hover:bg-gray-100
                                               dark:hover:bg-gray-700/50 transition"
                                    >
                                        {lockIcon(accessState)} {link.label}
                                    </button>
                                {/if}
                            {/each}
                        </div>
                    {/if}
                {/if}
            </div>
        {/each}
    </div>
</div>
{/if}
