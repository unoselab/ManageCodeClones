import * as vscode from 'vscode';

class DropItem extends vscode.TreeItem {
    constructor(public readonly label: string, public readonly content: string) {
        super(label, vscode.TreeItemCollapsibleState.None);
        this.tooltip = content;
        this.description = "Code Snippet";
    }
}

class DropzoneProvider implements vscode.TreeDataProvider<DropItem>, vscode.TreeDragAndDropController<DropItem> {
    private dropItems: DropItem[] = [];

    private _onDidChangeTreeData: vscode.EventEmitter<DropItem | undefined | void> = new vscode.EventEmitter<DropItem | undefined | void>();
    readonly onDidChangeTreeData: vscode.Event<DropItem | undefined | void> = this._onDidChangeTreeData.event;

    dropMimeTypes = ['text/plain'];
    dragMimeTypes = ['text/plain']; 

    getTreeItem(element: DropItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: DropItem): vscode.ProviderResult<DropItem[]> {
        if (element) {
            return [];
        }
        return this.dropItems; 
    }

    public addSnippet(textContent: string) {
        const label = textContent.trim().substring(0, 20).replace(/\n/g, ' ') + '...';
        const newItem = new DropItem(label, textContent);
        this.dropItems.push(newItem);
        this._onDidChangeTreeData.fire();
    }

    async handleDrop(target: DropItem | undefined, dataTransfer: vscode.DataTransfer, token: vscode.CancellationToken): Promise<void> {
        // Drop logic remains the same
    }

    async handleDrag(source: readonly DropItem[], dataTransfer: vscode.DataTransfer, token: vscode.CancellationToken): Promise<void> {
        if (source.length === 0) {
            return;
        }
        const draggedItem = source[0];
        const transferItem = new vscode.DataTransferItem(draggedItem.content);
        dataTransfer.set('text/plain', transferItem);
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('Dropzone Extension is now active!');

    const dropzoneProvider = new DropzoneProvider();

    const treeView = vscode.window.createTreeView('dragDropZone', {
        treeDataProvider: dropzoneProvider,
        dragAndDropController: dropzoneProvider
    });

    const addSnippetCmd = vscode.commands.registerCommand('dragDropZone.addSnippet', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const selection = editor.selection;
            const text = editor.document.getText(selection);
            
            if (text) {
                dropzoneProvider.addSnippet(text);
                vscode.window.showInformationMessage('Added to Dropzone!');
            } else {
                vscode.window.showWarningMessage('Please highlight some text first.');
            }
        }
    });

    context.subscriptions.push(treeView);
    context.subscriptions.push(addSnippetCmd);
}

export function deactivate() {}