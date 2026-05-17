<script>
    import SyllabusSidebarMenu from './SyllabusSidebarMenu.svelte';
    import HistoryTracker from './HistoryTracker.svelte';
</script>

<!--
    Anchor.svelte — Custom extension injection point in the native Sidebar.

    Renders:
      1. HistoryTracker  — headless; tags new chats with syllabus metadata.
      2. SyllabusSidebarMenu — shows Trial (always_active plan) content tree.
         Buttons in this tree are always unlocked (no entitlement check needed).

    Paid content is navigated via the BreadcrumbBar injected into Chat.svelte.
    The native sidebar-chats section (chat history list) is completely untouched.
-->
<div class="custom-extensions-anchor pb-2">
    <!-- Headless — renders nothing, manages HistoryTracker race-condition guards -->
    <HistoryTracker />

    <!-- Trial content tree — always visible, always unlocked -->
    <SyllabusSidebarMenu />
</div>
