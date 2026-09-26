import UIKit
import UniformTypeIdentifiers

class ShareController:UIViewController {
    let status=UILabel()
    override func viewDidLoad(){
        super.viewDidLoad();view.backgroundColor = .systemBackground
        status.text="Saving to Lectic…";status.numberOfLines=0;status.textAlignment = .center;status.translatesAutoresizingMaskIntoConstraints=false
        view.addSubview(status);NSLayoutConstraint.activate([status.leadingAnchor.constraint(equalTo:view.leadingAnchor,constant:24),status.trailingAnchor.constraint(equalTo:view.trailingAnchor,constant:-24),status.centerYAnchor.constraint(equalTo:view.centerYAnchor)])
        Task{await save()}
    }
    func save() async {
        do{
            let providers=(extensionContext?.inputItems as? [NSExtensionItem] ?? []).flatMap{$0.attachments ?? []}
            guard !providers.isEmpty,providers.count<=20 else{throw QueueError.message("Share up to 20 items at a time.")}
            for provider in providers {
                if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier){
                    let value=try await load(provider,UTType.url.identifier)
                    if let url=value as? URL {
                        if url.isFileURL { try CaptureQueue.shared.saveFile(url,name:url.lastPathComponent) }
                        else { try CaptureQueue.shared.saveText(url.absoluteString) }
                    }
                    else { throw QueueError.message("This link could not be saved. Try sharing its text.") }
                }else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier){
                    let value=try await load(provider,UTType.plainText.identifier)
                    guard let text=value as? String else{throw QueueError.message("This text could not be read.")}
                    try CaptureQueue.shared.saveText(text)
                }else{
                    guard let type=provider.registeredTypeIdentifiers.first(where:{id in guard let type=UTType(id) else{return false};return type.conforms(to:.image)||type.conforms(to:.movie)||type.conforms(to:.audio)||type.conforms(to:.pdf)||type.conforms(to:.data)}) else{throw QueueError.message("Share a URL, text, image, PDF, audio or video.")}
                    try await withCheckedThrowingContinuation{(continuation:CheckedContinuation<Void,Error>) in
                        provider.loadFileRepresentation(forTypeIdentifier:type){url,error in
                            guard let url=url else{continuation.resume(throwing:error ?? QueueError.message("File unavailable."));return}
                            do{let ext=UTType(type)?.preferredFilenameExtension ?? url.pathExtension
                                let name=provider.suggestedName ?? "Shared file"
                                try CaptureQueue.shared.saveFile(url,name:name.contains(".") ? name : name+"."+ext)
                                continuation.resume()
                            }catch{continuation.resume(throwing:error)}
                        }
                    }
                }
            }
            await withCheckedContinuation { (continuation:CheckedContinuation<Void,Never>) in
                CaptureQueue.shared.retry { continuation.resume() }
            }
            status.text="Saved on this phone. Uploads continue in the background."
            // Acknowledge only after every supplied file/text item has a durable local copy.
            extensionContext?.completeRequest(returningItems:nil)
        }catch{
            status.text=error.localizedDescription+"\nAny items already saved remain in Lectic."
            let close=UIButton(type:.system);close.setTitle("Close",for:.normal);close.addTarget(self,action:#selector(cancel),for:.touchUpInside);close.translatesAutoresizingMaskIntoConstraints=false;view.addSubview(close)
            NSLayoutConstraint.activate([close.centerXAnchor.constraint(equalTo:view.centerXAnchor),close.topAnchor.constraint(equalTo:status.bottomAnchor,constant:24)])
        }
    }
    func load(_ provider:NSItemProvider,_ type:String) async throws -> NSSecureCoding {
        try await withCheckedThrowingContinuation{continuation in provider.loadItem(forTypeIdentifier:type,options:nil){item,error in
            if let error=error{continuation.resume(throwing:error)}else if let item=item{continuation.resume(returning:item)}else{continuation.resume(throwing:QueueError.message("Nothing was shared."))}
        }}
    }
    @objc func cancel(){extensionContext?.cancelRequest(withError:QueueError.message("Share closed."))}
}
