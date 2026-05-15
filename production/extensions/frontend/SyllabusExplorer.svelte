<script>
	import { onMount } from 'svelte';

	// --- State Variables ---
	let syllabusTree = {};
	let loading = true;
	let error = null;

	// Dropdown Selections
	let selectedExam = '';
	let selectedSubject = '';
	let selectedTopic = '';
	let selectedLesson = '';

	// Computed Options based on selections
	$: exams = Object.keys(syllabusTree);
	$: subjects = selectedExam
		? Object.keys(syllabusTree[selectedExam] || {}).filter((k) => !k.startsWith('_'))
		: [];
	$: topics = selectedSubject
		? Object.keys(syllabusTree[selectedExam][selectedSubject] || {}).filter(
				(k) => !k.startsWith('_')
			)
		: [];
	$: lessons = selectedTopic
		? Object.keys(syllabusTree[selectedExam][selectedSubject][selectedTopic] || {}).filter(
				(k) => !k.startsWith('_')
			)
		: [];

	// The prompts available in the finally selected lesson
	$: availablePrompts = selectedLesson
		? syllabusTree[selectedExam][selectedSubject][selectedTopic][selectedLesson]['_prompts'] || []
		: [];

	onMount(async () => {
		try {
			// Fetch the syllabus index from our custom backend extension
			const response = await fetch('/api/ext/syllabus/index');
			if (!response.ok) throw new Error('Failed to load syllabus');
			syllabusTree = await response.json();

			// Check for trial limitations here if needed (e.g., locking certain subjects)
		} catch (err) {
			error = err.message;
		} finally {
			loading = false;
		}
	});

	// --- Handlers ---

	// Reset child dropdowns when a parent changes
	function onExamChange() {
		selectedSubject = '';
		selectedTopic = '';
		selectedLesson = '';
	}
	function onSubjectChange() {
		selectedTopic = '';
		selectedLesson = '';
	}
	function onTopicChange() {
		selectedLesson = '';
	}

	// Intercept prompt click to send to our custom backend router
	async function handlePromptClick(promptFilename) {
		// Here we would extract the data-* attributes from the HTML payload if needed,
		// or just pass the file identifier to the backend.

		const payload = {
			endpoint_type: 'notes', // or 'mcq' depending on the button clicked
			exam: selectedExam,
			subject: selectedSubject,
			topic: selectedTopic,
			lesson: selectedLesson,
			prompt_text: promptFilename // We pass the identifier, backend parses the actual HTML
		};

		try {
			// 1. Send to our custom router (ext_router.py) to check cache & subscription
			const res = await fetch('/api/ext/generate', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (res.status === 403) {
				alert('Active premium subscription required to access this note.');
				return;
			}

			const data = await res.json();

			// 2. Inject the response into the Open WebUI native chat interface
			// (In reality, we would dispatch an event to the main chat component)
			console.log('AI Response:', data.response_text);
			console.log('Was Cached:', data.is_cached);
		} catch (err) {
			console.error('Generation failed:', err);
		}
	}
</script>

<div class="syllabus-explorer bg-gray-50 dark:bg-gray-900 p-6 rounded-xl shadow-sm">
	<h2 class="text-2xl font-bold mb-4 text-gray-800 dark:text-gray-100">CSIR/GATE Study Material</h2>

	{#if loading}
		<div class="animate-pulse flex space-x-4">
			<div class="h-10 bg-gray-300 rounded w-1/4"></div>
			<div class="h-10 bg-gray-300 rounded w-1/4"></div>
			<div class="h-10 bg-gray-300 rounded w-1/4"></div>
			<div class="h-10 bg-gray-300 rounded w-1/4"></div>
		</div>
	{:else if error}
		<p class="text-red-500">Error loading syllabus: {error}</p>
	{:else}
		<!-- Cascading Dropdowns -->
		<div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
			<!-- Exam Select -->
			<select
				bind:value={selectedExam}
				on:change={onExamChange}
				class="block text-sm focus:ring-blue-500 focus:border-blue-500 w-full rounded-lg border-gray-300 dark:bg-gray-800 dark:border-gray-700"
			>
				<option value="">-- Exam --</option>
				{#each exams as exam}
					<option value={exam}>{exam.toUpperCase()}</option>
				{/each}
			</select>

			<!-- Subject Select -->
			<select
				bind:value={selectedSubject}
				on:change={onSubjectChange}
				disabled={!selectedExam}
				class="block text-sm focus:ring-blue-500 focus:border-blue-500 w-full rounded-lg border-gray-300 dark:bg-gray-800 dark:border-gray-700 disabled:opacity-50"
			>
				<option value="">-- Subject --</option>
				{#each subjects as subject}
					<!-- Implement Trial Lock Logic Here -->
					<option value={subject}>{subject.replace(/_/g, ' ')}</option>
				{/each}
			</select>

			<!-- Topic Select -->
			<select
				bind:value={selectedTopic}
				on:change={onTopicChange}
				disabled={!selectedSubject}
				class="block text-sm focus:ring-blue-500 focus:border-blue-500 w-full rounded-lg border-gray-300 dark:bg-gray-800 dark:border-gray-700 disabled:opacity-50"
			>
				<option value="">-- Topic --</option>
				{#each topics as topic}
					<option value={topic}>{topic.replace(/_/g, ' ')}</option>
				{/each}
			</select>

			<!-- Lesson Select -->
			<select
				bind:value={selectedLesson}
				disabled={!selectedTopic}
				class="block text-sm focus:ring-blue-500 focus:border-blue-500 w-full rounded-lg border-gray-300 dark:bg-gray-800 dark:border-gray-700 disabled:opacity-50"
			>
				<option value="">-- Lesson --</option>
				{#each lessons as lesson}
					<option value={lesson}>{lesson.replace(/_/g, ' ')}</option>
				{/each}
			</select>
		</div>

		<!-- Render Prompts as Cards -->
		{#if selectedLesson && availablePrompts.length > 0}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 border-t pt-6 dark:border-gray-700">
				{#each availablePrompts as prompt}
					<div
						class="prompt-card bg-white dark:bg-gray-800 p-4 rounded-lg shadow border border-gray-200 dark:border-gray-700 hover:shadow-md transition"
					>
						<h4 class="font-semibold text-lg mb-2 text-gray-800 dark:text-gray-200">
							{prompt.replace('.html', '').replace(/_/g, ' ')}
						</h4>
						<div class="flex space-x-2 mt-4">
							<button
								on:click={() => handlePromptClick(prompt)}
								class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition"
							>
								📖 Generate Study Notes
							</button>
							<!-- MCQ buttons would trigger a different endpoint_type -->
							<button
								class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded-md transition"
							>
								📝 Practice MCQ
							</button>
						</div>
					</div>
				{/each}
			</div>
		{:else if selectedLesson}
			<p class="mt-6 text-gray-500 italic text-center">
				No study materials available for this lesson yet.
			</p>
		{/if}
	{/if}
</div>


