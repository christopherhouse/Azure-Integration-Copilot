/**
 * Global type augmentation for the runtime configuration object injected
 * by the {@link RuntimeConfig} server component via a `<script>` tag.
 */
interface RuntimeConfig {
  apiBaseUrl?: string;
}

interface Window {
  __RUNTIME_CONFIG__?: RuntimeConfig;
}
