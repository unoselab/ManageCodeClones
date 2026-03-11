import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    console.log('Extension "drag" is now active!');

    // Listen to all text changes happening in the editor
    const disposable = vscode.workspace.onDidChangeTextDocument(event => {
        const changes = event.contentChanges;

        // A native drag-and-drop move creates exactly two changes in a SINGLE event: 
        // 1. A deletion of the highlighted text at the source.
        // 2. An insertion of that text at the destination.
        if (changes.length === 2) {
            
            // Find which change represents the deletion and which is the insertion
            const deletion = changes.find(c => c.text === '' && c.rangeLength > 0);
            const insertion = changes.find(c => c.text !== '' && c.rangeLength === 0);

            if (deletion && insertion) {
                if (deletion.rangeLength === insertion.text.length) {
                    
                    console.log('Internal Drag & Drop Detected!');
                    console.log(`Moved text: "${insertion.text}"`);
                    vscode.window.showInformationMessage(`You dragged and dropped: "${insertion.text}"`);
                }
            }
        }
    });

    context.subscriptions.push(disposable);
}

export function deactivate() {}