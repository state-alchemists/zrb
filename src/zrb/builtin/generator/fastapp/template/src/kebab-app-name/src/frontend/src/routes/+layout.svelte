<script lang="ts">
  	import "../app.css";
	import Navigation from '$lib/components/navigation/Navigation.svelte';
	import {navData} from '$lib/config/navData';
	import {appBrand, appTitle, appAuthTokenCookieKey} from '$lib/config/config';
	import logo from '/static/logo.png';
</script>

<title>{appTitle}</title>
<Navigation data={navData} logo={logo} brand={appBrand} authTokenCookieKey={appAuthTokenCookieKey}></Navigation>
<div class="pl-10 pr-10">
	<slot></slot>
</div>
