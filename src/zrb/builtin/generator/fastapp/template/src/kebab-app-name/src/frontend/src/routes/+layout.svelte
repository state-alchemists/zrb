<script lang="ts">
    import { onMount } from 'svelte';
	import Navigation from '$lib/components/navigation/Navigation.svelte';
	import { navData } from '$lib/config/navData';
	import { appBrand, appTitle, appRefreshTokenSeconds } from '$lib/config/config';
    import { refreshToken } from '$lib/auth/auth';
	import logo from '/static/logo.png';
  	import "../app.css";

	onMount(() => {
		setInterval(() => {
			refreshToken();
		}, appRefreshTokenSeconds * 1000)
	});
</script>

<title>{appTitle}</title>
<Navigation navData={navData} logo={logo} brand={appBrand}></Navigation>
<div class="pl-10 pr-10">
	<slot></slot>
</div>
