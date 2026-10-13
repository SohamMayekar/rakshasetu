# The landing page's hero picture

The hero shows a wide picture behind the phone. Until a photograph is added, a drawn dawn scene
stands in, so the page is never empty and never shows a broken image.

**To add it:** generate an image with any image tool (ChatGPT / DALL·E, Midjourney, Firefly, Imagen), then save it as

- `apps/web/public/images/hero.webp` (preferred, under 250 KB), or
- `apps/web/public/images/hero.jpg`

No code change is needed: the page tries `hero.webp`, then `hero.jpg`, then falls back to the drawn scene.

## Specs
- Wide, **16:9** (for example 2400 × 1350 px). It sits behind the phone at the bottom of the hero, so keep the subject low and in the centre.
- Light, airy, first light or early morning. Soft blue sky at the top, warm light low on the horizon.
- Keep the **upper half** calm sky: the headline and the phone sit over it.
- No text, no logos, no watermarks, no readable signs. No identifiable faces (keep people small or from behind).
- India context, dignified, hopeful, not distressing, and not about any single kind of disaster or team.

## Prompt (copy and paste)

> A calm, hopeful, photorealistic photograph at first light of first responders in high-visibility gear helping a
> family out of a damaged neighbourhood on the edge of an Indian town. People are small in frame and seen from behind or
> at a distance: two responders, an adult carrying a child, an elderly man with a blanket. Soft peach sunrise over
> hills and a footbridge in the far distance, light mist, long shadows, a few trees and low concrete houses, a rescue
> vehicle with a soft light bar parked at the edge of frame. Soft blue sky fading to warm cream at the horizon. It must
> not read as one specific disaster: no water level, no flames, no smoke, no rubble close up. Cinematic, natural
> colour, gentle contrast, documentary realism, no text, no logos, no watermark. Wide 16:9, subject in the lower
> centre, the upper half calm sky.

## Negative guidance (if the tool supports it)
text, letters, logos, watermark, distorted hands, extra limbs, close-up faces, gore, injury, cartoon, neon, purple haze.

## Why not generate it here
The build environment has no image-generation tool. The prompt above is written to give a picture that suits the page.
