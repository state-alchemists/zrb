<script lang="ts">
  	import "../app.css";
	import Navigation from '$lib/components/navigation/Navigation.svelte';
	import {navData} from '$lib/config/navData';
	import {appBrand, appTitle, appAuthTokenCookieKey} from '$lib/config/config';
	import logo from '$lib/assets/logo.png';
</script>

<title>{appTitle}</title>
<Navigation data={navData} logo={logo} brand={appBrand}, tokenCookieKey={appAuthTokenCookieKey}></Navigation>
<div class="pl-10 pr-10">
	<slot></slot>
</div>
