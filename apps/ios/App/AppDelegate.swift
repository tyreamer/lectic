import UIKit
import AuthenticationServices
import CryptoKit
import Security

@main
class AppDelegate:UIResponder,UIApplicationDelegate {
    var window:UIWindow?
    func application(_ application:UIApplication,didFinishLaunchingWithOptions options:[UIApplication.LaunchOptionsKey:Any]?) -> Bool {
        window=UIWindow(frame:UIScreen.main.bounds);window?.rootViewController=UINavigationController(rootViewController:LibraryController());window?.makeKeyAndVisible();return true
    }
    func application(_ application:UIApplication,handleEventsForBackgroundURLSession identifier:String,completionHandler:@escaping()->Void) {
        CaptureQueue.shared.handleEvents(identifier,completion:completionHandler)
    }
}

class LibraryController:UITableViewController,ASWebAuthenticationPresentationContextProviding {
    var rows:[PendingCapture]=[]
    var authSession:ASWebAuthenticationSession?
    override func viewDidLoad(){
        super.viewDidLoad();title="Lectic"
        navigationItem.rightBarButtonItem=UIBarButtonItem(title:"Library ↗",style:.plain,target:self,action:#selector(openLibrary))
        navigationItem.leftBarButtonItem=UIBarButtonItem(title:"Sign in",style:.plain,target:self,action:#selector(signIn))
        refreshControl=UIRefreshControl();refreshControl?.addTarget(self,action:#selector(retry),for:.valueChanged)
        let label=UILabel();label.text="Share from any app → Lectic\nPull down to retry saved uploads.";label.numberOfLines=0;label.textAlignment = .center;label.frame.size.height=100
        tableView.tableHeaderView=label
        NotificationCenter.default.addObserver(self,selector:#selector(retry),name:UIApplication.didBecomeActiveNotification,object:nil)
        retry()
    }
    @objc func retry(){Task{do{try await AuthAPI.refresh();CaptureQueue.shared.retry()}catch{show(error.localizedDescription)};rows=PendingCapture.all();tableView.reloadData();refreshControl?.endRefreshing()}}
    @objc func openLibrary(){UIApplication.shared.open(URL(string:Pilot.origin)!) }
    @objc func signIn(){
        let alert=UIAlertController(title:"Sign in to Lectic",message:"Use the email on your pilot invitation.",preferredStyle:.actionSheet)
        for provider in ["google","apple"]{alert.addAction(UIAlertAction(title:"Continue with "+provider.capitalized,style:.default){_ in self.authorize(provider)})}
        alert.addAction(UIAlertAction(title:"Cancel",style:.cancel));alert.popoverPresentationController?.barButtonItem=navigationItem.leftBarButtonItem;present(alert,animated:true)
    }
    func authorize(_ provider:String){Task{
        do{
            let config=try await AuthAPI.configuration()
            guard let base=config["supabaseUrl"] as? String,!base.isEmpty else{throw QueueError.message("Pilot sign-in is not configured yet.")}
            var bytes=[UInt8](repeating:0,count:32);guard SecRandomCopyBytes(kSecRandomDefault,bytes.count,&bytes)==errSecSuccess else{return}
            let verifier=Data(bytes).base64EncodedString().replacingOccurrences(of:"+",with:"-").replacingOccurrences(of:"/",with:"_").replacingOccurrences(of:"=",with:"")
            let challenge=Data(SHA256.hash(data:Data(verifier.utf8))).base64EncodedString().replacingOccurrences(of:"+",with:"-").replacingOccurrences(of:"/",with:"_").replacingOccurrences(of:"=",with:"")
            var url=URLComponents(string:base+"/auth/v1/authorize")!
            url.queryItems=[URLQueryItem(name:"provider",value:provider),URLQueryItem(name:"redirect_to",value:"lectic://auth"),URLQueryItem(name:"code_challenge",value:challenge),URLQueryItem(name:"code_challenge_method",value:"s256")]
            authSession=ASWebAuthenticationSession(url:url.url!,callbackURLScheme:"lectic"){callback,error in
                guard let callback=callback,callback.host=="auth",let code=URLComponents(url:callback,resolvingAgainstBaseURL:false)?.queryItems?.first(where:{$0.name=="code"})?.value else{return}
                Task{@MainActor in do{try await AuthAPI.exchange(code:code,verifier:verifier);self.retry()}catch{self.show(error.localizedDescription)}}
            }
            authSession?.presentationContextProvider=self;authSession?.start()
        }catch{show(error.localizedDescription)}
    }}
    func presentationAnchor(for session:ASWebAuthenticationSession)->ASPresentationAnchor{view.window!}
    func show(_ message:String){let alert=UIAlertController(title:"Lectic",message:message,preferredStyle:.alert);alert.addAction(UIAlertAction(title:"OK",style:.default));present(alert,animated:true)}
    override func tableView(_ tableView:UITableView,numberOfRowsInSection section:Int)->Int{rows.count}
    override func tableView(_ tableView:UITableView,cellForRowAt indexPath:IndexPath)->UITableViewCell{
        let item=rows[indexPath.row];let cell=UITableViewCell(style:.subtitle,reuseIdentifier:nil);cell.textLabel?.text=item.title;cell.detailTextLabel?.text=item.state;cell.imageView?.image=UIImage(systemName:item.state=="Uploaded" ? "checkmark.circle" : "tray.and.arrow.down");return cell
    }
}
