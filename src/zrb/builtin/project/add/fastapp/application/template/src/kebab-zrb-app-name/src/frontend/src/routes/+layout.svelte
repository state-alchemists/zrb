<script lang="ts">
    import { onMount } from 'svelte';
	import Navigation from '$lib/components/navigation/Navigation.svelte';
	import { navData } from '$lib/config/navData';
	import { getBrand, getTitle } from '$lib/config/app';
	import logo from '/static/logo.png';
  	import "../app.css";

	let appBrand = '';
	let appTitle = '';
	onMount(async () => {
		appBrand = await getBrand();	
		appTitle = await getTitle();	
	})
</script>

<title>{appTitle}</title>
<Navigation navData={navData} logo={logo} brand={appBrand}></Navigation>
<div class="pl-10 pr-10">
	<slot></slot>
</div>
