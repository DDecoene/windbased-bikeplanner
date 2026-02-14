<script lang="ts">
	import { SignedIn, SignedOut, UserButton } from 'svelte-clerk';
</script>

<div class="fixed top-4 right-4 z-50 flex items-center gap-3">
	<SignedIn>
		<UserButton
			appearance={{
				elements: {
					avatarBox: 'w-9 h-9 ring-2 ring-cyan-500/30',
					userButtonPopoverCard: 'bg-gray-900 border border-gray-700',
					userButtonPopoverActions: 'text-gray-300',
					userButtonPopoverActionButton: 'hover:bg-gray-800 text-gray-300',
					userButtonPopoverFooter: 'hidden'
				}
			}}
		/>
	</SignedIn>
	<SignedOut>
		<a
			href="/sign-in"
			class="rounded-lg border border-gray-700 bg-gray-900/80 px-4 py-2 text-sm font-medium text-gray-300 transition hover:border-cyan-500/50 hover:text-cyan-400"
		>
			Inloggen
		</a>
	</SignedOut>
</div>
