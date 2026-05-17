<script>
    import { onMount } from 'svelte';
    import { selectedTopic } from './syllabusStore.js';

    // ── State ──────────────────────────────────────────────────────────────────

    /** Full syllabus tree from /api/ext/syllabus/index */
    let fullTree = {};
    let treeLoaded = false;
    let loadError = false;

    /**
     * levels[i] = array of { key, label } options for dropdown at depth i.
     * Grows as the user makes selections; shrinks when a higher-level selection
     * changes.  Variable length — handles any folder depth automatically.
     */
    let levels = [];

    /**
     * selections[i] = the currently chosen key at depth i, or null if not yet chosen.
     * selections.length always equals levels.length.
     */
    let selections = [];

    /** True when the leaf of the current selection path has _files ready to show. */
    let showButtonEnabled = false;

    // ── Lifecycle ──────────────────────────────────────────────────────────────

    onMount(async () => {
        try {
            const res = await fetch('/api/ext/syllabus/index');
            if (res.ok) {
                fullTree = await res.json();
                treeLoaded = true;
                initLevels();
            } else {
                loadError = true;
            }
        } catch (err) {
            console.error('[BreadcrumbBar] Failed to load syllabus index:', err);
            loadError = true;
        }
    });

    // ── Tree navigation helpers ────────────────────────────────────────────────

    /**
     * Get child folder options from a tree node.
     * Filters out internal '_' keys (_files, _meta) and sorts alphabetically.
     */
    function getOptions(node) {
        if (!node || typeof node !== 'object') return [];
        return Object.keys(node)
            .filter((k) => !k.startsWith('_'))
            .sort()
            .map((k) => ({ key: k, label: formatFolderName(k) }));
    }

    /** Traverse fullTree along a path array and return the node at the end. */
    function getNodeAt(path) {
        let cursor = fullTree;
        for (const key of path) {
            if (!cursor || typeof cursor !== 'object') return {};
            cursor = cursor[key] ?? {};
        }
        return cursor;
    }

    /** True when this node has lesson HTML files and no more subfolders. */
    function nodeIsLeaf(node) {
        const hasFiles    = Array.isArray(node._files) && node._files.length > 0;
        const hasChildren = Object.keys(node).some((k) => !k.startsWith('_'));
        return hasFiles && !hasChildren;
    }

    /**
     * Resolve folder_key from _meta at the course level (depth index 1).
     * The course-level folder is always the second segment of the path
     * (exam_folder/course_folder) because metadata.json lives there.
     * Falls back to '' if _meta is absent (older content without metadata.json).
     */
    function resolveFolderKey(path) {
        if (path.length < 2) return '';
        let cursor = fullTree;
        for (let i = 0; i < 2; i++) {
            cursor = (cursor?.[path[i]]) ?? {};
        }
        return cursor._meta?.folder_key ?? '';
    }

    // ── Human-readable label ───────────────────────────────────────────────────

    function formatFolderName(name) {
        if (!name) return '';
        // Convert snake_case / ALL_CAPS to Title Case words.
        return name
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (c) => c.toUpperCase());
    }

    // ── Dropdown interaction ───────────────────────────────────────────────────

    /** Bootstrap the first dropdown from the tree root. */
    function initLevels() {
        const rootOptions = getOptions(fullTree);
        if (rootOptions.length === 0) return;
        levels     = [{ options: rootOptions }];
        selections = [null];
        showButtonEnabled = false;
    }

    /**
     * Called when the user picks an option in dropdown at index `depth`.
     * Resets everything deeper and either:
     *   - appends the next dropdown level, or
     *   - enables the Show button if we've reached a leaf.
     */
    function onSelect(depth, event) {
        const key = event.target.value || null;

        // Truncate selections and levels to current depth + 1.
        selections = [...selections.slice(0, depth), key];
        levels     = [...levels.slice(0, depth + 1)];
        showButtonEnabled = false;

        if (!key) return;   // user picked the placeholder "—"

        const validPath = selections.filter(Boolean);
        const node = getNodeAt(validPath);

        if (nodeIsLeaf(node)) {
            // We've reached a folder with HTML files and no more subfolders.
            showButtonEnabled = true;
        } else {
            const children = getOptions(node);
            if (children.length > 0) {
                levels     = [...levels, { options: children }];
                selections = [...selections, null];
            }
            // If children is empty AND no _files, this is an empty folder — do nothing.
        }
    }

    // ── Show button ───────────────────────────────────────────────────────────

    function handleShow() {
        const validPath = selections.filter(Boolean);
        const node      = getNodeAt(validPath);
        const files     = node._files || [];
        const folderKey = resolveFolderKey(validPath);

        selectedTopic.set({
            pathKeys:   validPath,
            pathLabels: validPath.map(formatFolderName),
            folderKey,
            files,
        });
    }

    // ── Breadcrumb click — navigate up ────────────────────────────────────────

    /**
     * Clicking a breadcrumb label resets selection to that depth.
     * Clears selectedTopic so LessonCardPanel hides.
     */
    function navigateTo(depth) {
        selections = [...selections.slice(0, depth + 1)];
        levels     = [...levels.slice(0, depth + 1)];
        showButtonEnabled = false;
        selectedTopic.set(null);

        // Re-evaluate leaf state for the truncated path.
        const validPath = selections.filter(Boolean);
        if (validPath.length === depth + 1) {
            const node = getNodeAt(validPath);
            if (nodeIsLeaf(node)) showButtonEnabled = true;
        }
    }

    // ── Reactive breadcrumb label list ────────────────────────────────────────
    // Derived from selections: only include levels where a key is chosen.
    $: breadcrumbItems = selections
        .map((key, i) => (key ? { key, label: formatFolderName(key), depth: i } : null))
        .filter(Boolean);
</script>

<!--
    BreadcrumbBar — secondary navigation bar injected below the native Navbar.

    Layout (flex row):
      [Exam ▼]  ›  [Course ▼]  ›  [Subject ▼]  ›  [Topic ▼]   [Show]

    Dropdowns are generated dynamically from the syllabus tree — any folder
    depth is supported without code changes.  The Show button appears only when
    the selected path terminates at a folder that contains HTML lesson files.
-->

{#if treeLoaded}
<div class="ext-breadcrumb-bar w-full flex items-center gap-1 px-3 py-1.5
            bg-gray-50 dark:bg-gray-850
            border-b border-gray-200 dark:border-gray-700
            text-[11px] text-gray-700 dark:text-gray-300
            flex-wrap">

    <!-- Cascading dropdowns — one per tree level -->
    {#each levels as level, i}
        {#if i > 0}
            <!-- Separator -->
            <span class="text-gray-400 dark:text-gray-600 select-none mx-0.5">›</span>
        {/if}

        <select
            class="ext-bc-select bg-transparent border-none outline-none
                   text-[11px] text-gray-700 dark:text-gray-300
                   cursor-pointer hover:text-blue-600 dark:hover:text-blue-400
                   py-0 px-0.5 max-w-[160px] truncate"
            value={selections[i] ?? ''}
            on:change={(e) => onSelect(i, e)}
        >
            <option value="">— pick —</option>
            {#each level.options as opt}
                <option value={opt.key}>{opt.label}</option>
            {/each}
        </select>
    {/each}

    <!-- Spacer pushes Show button to the right -->
    <div class="flex-1" />

    <!-- Show button — appears once a leaf topic is selected -->
    {#if showButtonEnabled}
        <button
            on:click={handleShow}
            class="ml-2 px-3 py-1 text-[11px] font-semibold rounded
                   bg-blue-600 hover:bg-blue-700 text-white
                   dark:bg-blue-500 dark:hover:bg-blue-400
                   transition-colors whitespace-nowrap"
        >
            Show
        </button>
    {:else}
        <button
            disabled
            class="ml-2 px-3 py-1 text-[11px] font-semibold rounded
                   bg-gray-200 dark:bg-gray-700
                   text-gray-400 dark:text-gray-500
                   cursor-not-allowed whitespace-nowrap"
        >
            Show
        </button>
    {/if}
</div>

{:else if loadError}
<!-- Silent failure — a broken breadcrumb must not disrupt the native chat UI -->
<div class="w-full px-3 py-1 text-[10px] text-red-400 dark:text-red-500
            bg-red-50 dark:bg-red-900/20 border-b border-red-100 dark:border-red-800">
    Study Materials navigation unavailable — check backend connectivity.
</div>
{/if}

<style>
    /* Remove default <select> arrow on WebKit so the breadcrumb stays slim.
       A custom › separator is used instead. */
    .ext-bc-select {
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
    }
</style>
