#tag Class
Protected Class App
Inherits ConsoleApplication
	#tag Event
		Function Run(args() as String) As Integer
		  #Pragma Unused args
		  Try
		    Var output As FolderItem = SpecialFolder.Temporary.Child("xojo-automation-m1-result.txt")
		    Var stream As TextOutputStream = TextOutputStream.Create(output)
		    stream.Write("agentic-hold-v3")
		    stream.Close
		  Catch error As IOException
		    Return 1
		  End Try
		  For tick As Integer = 1 To 600
		    App.DoEvents(100)
		  Next
		  Return 0
		End Function
	#tag EndEvent
End Class
#tag EndClass
