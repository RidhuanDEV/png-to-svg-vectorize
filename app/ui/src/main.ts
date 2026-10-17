import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { applyAppearance } from './lib/prefs.svelte';

// theme, density and text size before the first paint (no flash of the wrong theme)
applyAppearance();

const target = document.getElementById('app');
if (!target) throw new Error('#app missing');

export default mount(App, { target });
