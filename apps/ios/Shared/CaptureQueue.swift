import Foundation
import Security

enum Pilot {
    static let origin = Bundle.main.object(forInfoDictionaryKey: "LECTIC_ORIGIN") as! String
    static let group = Bundle.main.object(forInfoDictionaryKey: "LECTIC_APP_GROUP") as! String
    static let keychainGroup = Bundle.main.object(forInfoDictionaryKey: "LECTIC_KEYCHAIN_GROUP") as! String
    static var root: URL {
        let url = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: group)!.appendingPathComponent("Captures", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}

enum SecureSession {
    static func save(_ data: Data) throws {
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:"lectic-session", kSecAttrAccessGroup as String:Pilot.keychainGroup]
        SecItemDelete(query as CFDictionary)
        var item = query
        item[kSecValueData as String] = data
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(item as CFDictionary,nil) == errSecSuccess else { throw QueueError.message("Could not save sign-in securely.") }
    }
    static func load() -> [String:Any]? {
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:"lectic-session", kSecAttrAccessGroup as String:Pilot.keychainGroup, kSecReturnData as String:true, kSecMatchLimit as String:kSecMatchLimitOne]
        var value: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary,&value) == errSecSuccess, let data=value as? Data else { return nil }
        return (try? JSONSerialization.jsonObject(with:data)) as? [String:Any]
    }
}

enum QueueError: Error, LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text)=self { return text }; return nil }
}

struct PendingCapture: Codable, Identifiable {
    var id=UUID().uuidString
    var title:String
    var text:String?
    var filename:String?
    var bytes:Int=0
    var state="Saved on this phone"
    var captureID:String?
    var operationID:String?
    var attempts:Int=0
    var created=Date()
    var folder:URL { Pilot.root.appendingPathComponent(id,isDirectory:true) }
    var file:URL { folder.appendingPathComponent("original") }
    func save() throws {
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        try JSONEncoder().encode(self).write(to:folder.appendingPathComponent("capture.json"),options:[.atomic,.completeFileProtectionUntilFirstUserAuthentication])
    }
    static func all() -> [PendingCapture] {
        let folders=(try? FileManager.default.contentsOfDirectory(at:Pilot.root,includingPropertiesForKeys:nil)) ?? []
        return folders.compactMap { try? JSONDecoder().decode(Self.self,from:Data(contentsOf:$0.appendingPathComponent("capture.json"))) }.sorted{$0.created > $1.created}
    }
    static func load(_ id:String) -> PendingCapture? { all().first{$0.id==id} }
}

final class CaptureQueue: NSObject, URLSessionDataDelegate {
    static let shared=CaptureQueue()
    private var completions:[String:()->Void]=[:]
    private var buffers:[String:Data]=[:]
    private let lock=NSLock()
    private var sessions:[String:URLSession]=[:]
    static let appSession="ai.lectic.pilot.upload.app"
    static let shareSession="ai.lectic.pilot.upload.share"
    var identifier:String { Bundle.main.bundleURL.pathExtension=="appex" ? Self.shareSession : Self.appSession }
    func session(_ id:String) -> URLSession {
        lock.lock(); defer{lock.unlock()}
        if let existing=sessions[id] { return existing }
        let configuration=URLSessionConfiguration.background(withIdentifier:id)
        configuration.sharedContainerIdentifier=Pilot.group
        configuration.sessionSendsLaunchEvents=true
        configuration.isDiscretionary=false
        configuration.waitsForConnectivity=true
        configuration.timeoutIntervalForResource=24*3600
        let session=URLSession(configuration:configuration,delegate:self,delegateQueue:nil)
        sessions[id]=session; return session
    }
    func handleEvents(_ id:String, completion:@escaping()->Void) {
        lock.lock();completions[id]=completion;lock.unlock();_ = session(id)
    }
    func urlSessionDidFinishEvents(forBackgroundURLSession session:URLSession) {
        lock.lock();let callback=completions.removeValue(forKey:session.configuration.identifier ?? "");lock.unlock()
        if let callback=callback { DispatchQueue.main.async(execute:callback) }
    }
    func saveText(_ text:String) throws {
        guard !text.isEmpty, text.utf8.count<=200000 else { throw QueueError.message("This shared text is too large.") }
        let capture=PendingCapture(title:String(text.prefix(120)),text:text)
        try capture.save()
    }
    func saveFile(_ source:URL, name:String) throws {
        let size=(try source.resourceValues(forKeys:[.fileSizeKey])).fileSize ?? 0
        guard size>0 && size<=100*1024*1024 else { throw QueueError.message("Choose a file under 100 MB.") }
        let capture=PendingCapture(title:String(name.prefix(120)),filename:name,bytes:size)
        try FileManager.default.createDirectory(at:capture.folder,withIntermediateDirectories:true)
        try FileManager.default.copyItem(at:source,to:capture.file)
        try FileManager.default.setAttributes([.protectionKey:FileProtectionType.completeUntilFirstUserAuthentication],ofItemAtPath:capture.file.path)
        // The pending record is committed only after the original is copied into the shared container.
        try capture.save()
    }
    func retry(completion:@escaping()->Void = {}) {
        let group=DispatchGroup()
        for var item in PendingCapture.all() where item.state != "Uploaded" {
            if item.attempts>=5 { item.attempts=0;try? item.save() }
            group.enter();schedule(item){group.leave()}
        }
        group.notify(queue:.main,execute:completion)
    }
    func schedule(_ original:PendingCapture, completion:@escaping()->Void = {}) {
        let session=session(identifier)
        session.getAllTasks { tasks in
            defer{completion()}
            guard !tasks.contains(where:{$0.taskDescription?.hasPrefix(original.id+"|")==true}) else{return}
            var item=PendingCapture.load(original.id) ?? original
            guard item.attempts<5 else{return}
            guard let token=SecureSession.load()?["access_token"] as? String else {
                item.state="Saved — open Lectic to sign in";try? item.save();return
            }
            var request=URLRequest(url:URL(string:Pilot.origin+"/api/v1/captures")!)
            request.setValue("Bearer "+token,forHTTPHeaderField:"Authorization")
            request.setValue(item.id,forHTTPHeaderField:"Idempotency-Key")
            let upload:URL;let stage:String
            if let captureID=item.captureID, item.filename != nil {
                request.url=URL(string:Pilot.origin+"/api/v1/captures/"+captureID+"/content")!
                request.httpMethod="PUT";request.setValue("application/octet-stream",forHTTPHeaderField:"Content-Type")
                upload=item.file;stage="file"
            } else {
                request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
                var body:[String:Any]=["title":item.title]
                if let filename=item.filename { body.merge(["kind":"upload","filename":filename,"size":item.bytes]){_,new in new} }
                else {
                    let text=item.text ?? ""
                    let detector=try? NSDataDetector(types:NSTextCheckingResult.CheckingType.link.rawValue)
                    let match=detector?.firstMatch(in:text,range:NSRange(text.startIndex...,in:text))
                    if let url=match?.url,["https","http"].contains(url.scheme ?? "") {
                        body["kind"]="url";body["url"]=url.absoluteString;body["text"]=text
                    }else{body["kind"]="note";body["text"]=text}
                }
                upload=item.folder.appendingPathComponent("request.json")
                do { try JSONSerialization.data(withJSONObject:body).write(to:upload,options:.atomic) }
                catch { item.state="Saved — retry needed";try? item.save();return }
                stage="create"
            }
            item.attempts += 1;item.state="Uploading";try? item.save()
            let task=session.uploadTask(with:request,fromFile:upload)
            task.taskDescription=item.id+"|"+stage;task.resume()
        }
    }
    func urlSession(_ session:URLSession,dataTask:URLSessionDataTask,didReceive data:Data) {
        let key=(session.configuration.identifier ?? "")+String(dataTask.taskIdentifier)
        lock.lock();defer{lock.unlock()}
        if (buffers[key]?.count ?? 0)+data.count<=100000 { buffers[key,default:Data()].append(data) }
    }
    func urlSession(_ session:URLSession,task:URLSessionTask,didCompleteWithError error:Error?) {
        let parts=(task.taskDescription ?? "").split(separator:"|")
        guard parts.count==2,var item=PendingCapture.load(String(parts[0])) else{return}
        let key=(session.configuration.identifier ?? "")+String(task.taskIdentifier)
        lock.lock();let raw=buffers.removeValue(forKey:key) ?? Data();lock.unlock()
        let status=(task.response as? HTTPURLResponse)?.statusCode ?? 0
        if error != nil || !(200..<300).contains(status) {
            item.state=status==401 ? "Saved — open Lectic to sign in again" : "Saved — retry needed"
            try? item.save();return
        }
        let body=(try? JSONSerialization.jsonObject(with:raw)) as? [String:Any]
        item.operationID=body?["operation_id"] as? String
        if parts[1]=="create", let filename=item.filename, !filename.isEmpty {
            guard let captureID=body?["capture_id"] as? String else{item.state="Saved — retry needed";try? item.save();return}
            item.captureID=captureID;item.attempts=0;item.state="Saved";try? item.save();schedule(item)
        }else{
            item.state="Uploaded";try? item.save()
            // Keep the original until the API durably acknowledges the upload.
            try? FileManager.default.removeItem(at:item.file)
        }
    }
}
