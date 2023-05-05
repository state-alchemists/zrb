<script lang="ts">
  	import "../app.css";
	import Navigation from '$lib/components/Navigation.svelte';
	import navigationData from '$lib/data/navData.json';
	import logo from '$lib/assets/logo.png';
</script>

<Navigation data={navigationData} logo={logo} brand="bearbrand"></Navigation>

<div class="pl-10 pr-10">
	<slot></slot>
</div>
