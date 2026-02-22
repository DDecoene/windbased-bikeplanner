<script lang="ts">
  export let title: string = '';
  export let description: string = '';
  export let path: string = '/';
  export let image: string = '/og-image.png';
  export let noindex: boolean = false;

  const siteUrl = 'https://rgwnd.app';
  const canonical = siteUrl + path;
  const imageUrl = image.startsWith('http') ? image : siteUrl + image;
</script>

<svelte:head>
  <title>{title}</title>
  {#if description}
    <meta name="description" content={description} />
  {/if}
  <meta property="og:title" content={title} />
  {#if description}
    <meta property="og:description" content={description} />
  {/if}
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonical} />
  <meta property="og:image" content={imageUrl} />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content={title} />
  <meta property="og:locale" content="nl_BE" />
  <meta property="og:site_name" content="RGWND" />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={title} />
  {#if description}
    <meta name="twitter:description" content={description} />
  {/if}
  <meta name="twitter:image" content={imageUrl} />
  <meta name="twitter:image:alt" content={title} />

  <link rel="canonical" href={canonical} />
  {#if noindex}
    <meta name="robots" content="noindex, nofollow" />
  {/if}
</svelte:head>
