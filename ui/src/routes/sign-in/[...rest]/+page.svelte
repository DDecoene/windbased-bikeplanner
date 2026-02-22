<script lang="ts">
	import { SignIn } from 'svelte-clerk';
import Meta from '$lib/Meta.svelte';
</script>

<Meta title="Inloggen — RGWND" description="Log in op RGWND om routes te genereren." path="/sign-in" noindex={true} />

<main class="flex min-h-screen items-center justify-center p-4">
	<div class="w-full max-w-md">
		<div class="mb-6 text-center">
			<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400"
				>&larr; Terug naar RGWND</a
			>
		</div>
		<SignIn
			routing="path"
			path="/sign-in"
			signUpUrl="/sign-up"
			appearance={{
				elements: {
					rootBox: 'mx-auto',
					card: 'bg-gray-900 border border-gray-800 shadow-xl',
					headerTitle: 'text-gray-100',
					headerSubtitle: 'text-gray-400',
					socialButtonsBlockButton: 'bg-gray-800 border-gray-700 text-gray-200 hover:bg-gray-700',
					formFieldLabel: 'text-gray-400',
					formFieldInput: 'bg-gray-800 border-gray-700 text-gray-100',
					formButtonPrimary: 'bg-cyan-500 hover:bg-cyan-400',
					footerActionLink: 'text-cyan-400 hover:text-cyan-300',
					dividerLine: 'bg-gray-700',
					dividerText: 'text-gray-500',
					formFieldInputShowPasswordButton: 'text-gray-400',
					identityPreviewEditButton: 'text-cyan-400',
					footer: 'hidden'
				}
			}}
		/>
	</div>
</main>
