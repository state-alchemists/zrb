<script lang="ts">
    import { page } from '$app/stores';
</script>
<div class="flex flex-col justify-center items-center">
    <h1 class="text-5xl">{$page.status}</h1>
    <p class="text-3xl">{$page.error?.message}</p>
    <a class="btn btn-primary mt-5" href="/">Let's go home</a>
</div>
