// Stable bridge from Camoufox's Python launch options to Playwright launchServer.
'use strict'

const path = require('path')

const driverPackage = process.argv[2]
let playwright
try {
    playwright = require(path.join(driverPackage, 'index.js'))
} catch (error) {
    console.error(`Error loading the Playwright driver from ${driverPackage}:`, error.message)
    process.exit(1)
}

process.stdin.setEncoding('utf8')

const stdinTerminated = new Promise((resolve) => {
    let settled = false
    const cleanup = () => {
        process.stdin.removeListener('end', onEnd)
        process.stdin.removeListener('close', onClose)
        process.stdin.removeListener('error', onError)
    }
    const finish = (error = null) => {
        if (settled)
            return
        settled = true
        cleanup()
        resolve(error)
    }
    const onEnd = () => finish()
    const onClose = () => finish()
    const onError = (error) => finish(error)

    process.stdin.once('end', onEnd)
    process.stdin.once('close', onClose)
    process.stdin.once('error', onError)
})

function parseOptions(data) {
    return JSON.parse(Buffer.from(data, 'base64').toString())
}

function collectData() {
    return new Promise((resolve, reject) => {
        let data = ''
        let settled = false
        const cleanup = () => {
            process.stdin.removeListener('data', onData)
            process.stdin.removeListener('end', onEnd)
            process.stdin.removeListener('close', onClose)
            process.stdin.removeListener('error', onError)
        }
        const finish = (encoded) => {
            if (settled)
                return
            settled = true
            cleanup()
            try {
                resolve(parseOptions(encoded))
            } catch (error) {
                reject(error)
            }
        }
        const onData = (chunk) => {
            data += chunk
            const newline = data.indexOf('\n')
            if (newline !== -1)
                finish(data.slice(0, newline))
        }
        const onEnd = () => finish(data)
        const onClose = () => finish(data)
        const onError = (error) => {
            if (settled)
                return
            settled = true
            cleanup()
            reject(error)
        }

        process.stdin.on('data', onData)
        process.stdin.once('end', onEnd)
        process.stdin.once('close', onClose)
        process.stdin.once('error', onError)
        process.stdin.resume()
    })
}

async function main() {
    const options = await collectData()
    // Playwright's shared BrowserServer mode exposes one long-lived context to
    // Selkies and every remote client instead of deleting it on disconnect.
    options._sharedBrowser = true
    console.info('Launching server...')
    const browserServer = await playwright.firefox.launchServer(options)
    const browserTerminated = new Promise((resolve) => {
        browserServer.once('close', (exitCode, signal) => resolve({ exitCode, signal }))
    })
    const browser = await playwright.firefox.connect(browserServer.wsEndpoint())
    const context = browser.contexts()[0] || await browser.newContext({ viewport: null })
    if (!context.pages().length)
        await context.newPage()
    console.log('Websocket endpoint:', browserServer.wsEndpoint())

    const termination = await Promise.race([
        stdinTerminated.then((error) => ({ source: 'stdin', error })),
        browserTerminated.then((details) => ({ source: 'browser', details })),
    ])
    if (termination.source === 'browser') {
        const { exitCode, signal } = termination.details
        throw new Error(`Camoufox browser terminated (exitCode=${exitCode}, signal=${signal})`)
    }
    await browserServer.close()
    if (termination.error)
        throw termination.error
}

main().catch((error) => {
    console.error('Error launching server:', error.stack || error.message)
    process.exit(1)
})
