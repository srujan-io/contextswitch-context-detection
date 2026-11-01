# Screenshot To Soul

Implement exactly the screenshot and nothing else

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/7826d12a-5979-4c12-8913-01574dabb607).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

## ContextSwitch extension integration

The popup UI is bundled into the ContextSwitch MV3 extension, and the extension service worker relays discrete CV sensor events to the UI. With both repositories checked out as sibling folders, run:

```sh
npm install
npm run build:extension
```

If the extension checkout is elsewhere, set `CONTEXTSWITCH_EXTENSION_DIR` to its `extension` folder before building. Then load or reload that ContextSwitch extension in Chrome/Edge. The UI defaults to isolated demo mode. Live CV events require turning demo mode off; the `/ws/cv` socket remains disabled unless `enableCvWebSocket` is explicitly set to `true` in the extension's `config.js`. Events are shown as detected sensor actions, not as browser execution results.
