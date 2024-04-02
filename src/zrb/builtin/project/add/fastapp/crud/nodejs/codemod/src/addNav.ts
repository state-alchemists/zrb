import { readFileSync, writeFileSync } from "fs";
import { ts, Project } from "ts-morph";

function appendNavigation(fileName: string, varName: string, title: string, url: string, permission: string) {
    const project = new Project();
    const content = readFileSync(fileName).toString();
    const sourceFile = project.createSourceFile('navigation.ts', content);

    sourceFile.transform(traversal => {
        const node = traversal.visitChildren();
        if (ts.isVariableDeclaration(node) && node.name.getText() === varName) {
            const arrayLiteral = traversal.factory.createArrayLiteralExpression([
                ...(node.initializer as ts.ArrayLiteralExpression)?.elements ?? [],
                traversal.factory.createIdentifier(
                    `{title: "${title}", url: "${url}", permission: "${permission}"}`
                )
            ]);
            return traversal.factory.updateVariableDeclaration(
                node,
                node.name,
                node.exclamationToken,
                node.type,
                arrayLiteral
            );
        }
        return node;
    });

    const modifiedContent = sourceFile.getText();
    writeFileSync(fileName, modifiedContent);
}

const fileName = process.argv[2];
const varName = process.argv[3];
const title = process.argv[4];
const url = process.argv[5];
const permission = process.argv[6];
appendNavigation(fileName, varName, title, url, permission);