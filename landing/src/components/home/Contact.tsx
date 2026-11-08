import { SignButton } from "@/components/site/SignButton";
import { TextField } from "./TextField";

const TOPICS = ["A shop or restaurant", "A building or campus", "Press", "Something else"] as const;

/** PROTOTYPE for design review: the contact section, above the closing piece. Not wired to an endpoint yet. */
export function Contact() {
	return (
		<section id="contact" aria-labelledby="contact-h" className="pad py-section">
			<div className="grid grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-16 border-t-[8px] border-ink pt-12 max-[900px]:grid-cols-1 max-[900px]:gap-10">
				<div className="flex flex-col gap-5">
					<span className="lbl">Contact</span>
					<h2
						id="contact-h"
						className="m-0 max-w-[16ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
					>
						Get in touch.
					</h2>
					<p className="m-0 max-w-[40ch] text-[20px] leading-[1.45]">
						Run a shop, manage a building, or just curious? Packet starts around University Village, and we want
						to hear from the people and places nearby.
					</p>
				</div>
				<form noValidate className="flex flex-col gap-7 self-end">
					<fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
						<legend className="lbl mb-3 p-0 text-[length:var(--field-label)]">This is about</legend>
						<div className="flex flex-wrap gap-2">
							{TOPICS.map((topic, i) => (
								<label
									key={topic}
									className="cursor-pointer border-[1.5px] border-ink px-3 py-2 text-[15px] has-[:checked]:bg-ink has-[:checked]:text-white"
								>
									<input type="radio" name="topic" value={topic} defaultChecked={i === 0} className="sr-only" />
									{topic}
								</label>
							))}
						</div>
					</fieldset>
					<div className="flex flex-wrap gap-6 max-[760px]:flex-col">
						<TextField id="contact-name" label="Your name" name="name" autoComplete="name" placeholder="First and last" />
						<TextField id="contact-email" label="Email" name="email" type="email" autoComplete="email" placeholder="you@example.com" />
					</div>
					<div className="flex">
						<TextField id="contact-org" label="Shop, building or company (optional)" name="org" autoComplete="organization" placeholder="Where you are" />
					</div>
					<div className="flex items-end gap-6 max-[760px]:flex-col max-[760px]:items-start">
						<TextField id="contact-msg" label="Message" name="message" placeholder="What you have in mind" />
						<SignButton label="Send" type="submit" />
					</div>
					<p className="m-0 min-h-6 text-[14px]">We only use this to reply to you.</p>
				</form>
			</div>
		</section>
	);
}
